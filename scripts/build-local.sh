#!/usr/bin/env bash
# ── Local build (skip Apple Developer ID signing & notarization) ──
# Produces dist/vvrite.dmg suitable for local testing.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ── Configuration ──────────────────────────────────────────────
BUNDLE="dist/vvrite.app"
ENTITLEMENTS="entitlements.plist"
DMG="dist/vvrite.dmg"
SPARKLE_ENABLED="${SPARKLE_ENABLED:-1}"
SPARKLE_VENDOR_DIR="${SPARKLE_VENDOR_DIR:-$ROOT_DIR/vendor/Sparkle}"
SPARKLE_FRAMEWORK="$SPARKLE_VENDOR_DIR/Sparkle.framework"
SPARKLE_KEY_ACCOUNT="${SPARKLE_KEY_ACCOUNT:-vvrite}"

# Codesigning identity. Ad-hoc ("-") has no stable identity, so every rebuild
# produces a new signature and macOS resets Accessibility/Microphone grants.
# A self-signed Code Signing cert in the login keychain keeps them across builds:
#   security find-identity -v -p codesigning
SIGN_IDENTITY="${SIGN_IDENTITY:-vvrite-dev}"
if ! security find-identity -v -p codesigning 2>/dev/null | grep -q "\"$SIGN_IDENTITY\""; then
    echo "▸ Identity '$SIGN_IDENTITY' not found — falling back to ad-hoc signing"
    echo "  (TCC permissions will reset on every rebuild)"
    SIGN_IDENTITY="-"
fi

# Use the Sparkle key for the configured account
if [[ -z "${SPARKLE_PUBLIC_ED_KEY:-}" ]]; then
    echo "▸ Looking up SPARKLE_PUBLIC_ED_KEY for account '$SPARKLE_KEY_ACCOUNT'..."
    export SPARKLE_PUBLIC_ED_KEY
    SPARKLE_PUBLIC_ED_KEY=$("$SPARKLE_VENDOR_DIR/bin/generate_keys" --account "$SPARKLE_KEY_ACCOUNT" -p 2>/dev/null || true)
    if [[ -z "$SPARKLE_PUBLIC_ED_KEY" ]]; then
        # Try again without -p to show helpful output
        "$SPARKLE_VENDOR_DIR/bin/generate_keys" --account "$SPARKLE_KEY_ACCOUNT" 2>&1
        echo ""
        echo "Extract the SUPublicEDKey from the output above and export it:"
        echo "  export SPARKLE_PUBLIC_ED_KEY=\"...\""
        exit 1
    fi
    echo "  ✓ Using SPARKLE_PUBLIC_ED_KEY=$SPARKLE_PUBLIC_ED_KEY"
fi

# ── Step 0: Preflight ───────────────────────────────────────────
echo "▸ Checking build environment..."
python - <<'PY'
import importlib
import sys

required_modules = {
    "ServiceManagement": "pyobjc-framework-ServiceManagement",
}

missing = []
for module_name, package_name in required_modules.items():
    try:
        importlib.import_module(module_name)
    except ImportError:
        missing.append(f"{package_name} ({module_name})")

if missing:
    details = "\n".join(f"  - {item}" for item in missing)
    raise SystemExit(
        "Missing required Python bridge modules:\n"
        f"{details}\n"
        "Run `pip install -r requirements.txt` and retry."
    )

print("  ✓ Required Python bridge modules available")
PY

if [[ "$SPARKLE_ENABLED" != "0" ]]; then
    "$ROOT_DIR/scripts/prepare_sparkle.sh"
fi

# ── Step 0.5: Backward-compatible metallib ────────────────────
MLX_COMPAT_DIR=$(mktemp -d)
MLX_METAL_VER=$(pip show mlx-metal | awk '/^Version:/{print $2}')
echo "▸ Fetching macOS 15-compatible mlx-metal $MLX_METAL_VER..."
pip download --no-deps -d "$MLX_COMPAT_DIR" \
    "mlx-metal==$MLX_METAL_VER" \
    --platform macosx_15_0_arm64 --only-binary :all: --quiet
SITE=$(python -c "import site; print(site.getsitepackages()[0])")
unzip -o "$MLX_COMPAT_DIR"/mlx_metal-*.whl "mlx/lib/mlx.metallib" -d "$SITE" > /dev/null
rm -rf "$MLX_COMPAT_DIR"
echo "  ✓ Backward-compatible metallib installed (macOS 15+)"

# ── Step 1: Build ──────────────────────────────────────────────
echo "▸ Building with PyInstaller..."
pyinstaller vvrite.spec --noconfirm
echo "  ✓ Build complete"

if [[ "$SPARKLE_ENABLED" != "0" ]]; then
    echo "▸ Embedding Sparkle.framework..."
    mkdir -p "$BUNDLE/Contents/Frameworks"
    rm -rf "$BUNDLE/Contents/Frameworks/Sparkle.framework"
    ditto "$SPARKLE_FRAMEWORK" "$BUNDLE/Contents/Frameworks/Sparkle.framework"
    echo "  ✓ Sparkle embedded"
fi

# ── Step 2: Sign (required for macOS to run the app) ──
echo "▸ Signing binaries and bundle with: $SIGN_IDENTITY"

# Sign .so and .dylib files first
find "$BUNDLE" -type f \( -name "*.so" -o -name "*.dylib" \) | while read -r lib; do
    codesign --force --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$SIGN_IDENTITY" \
        --timestamp \
        "$lib" 2>/dev/null
done

# Sign embedded frameworks (excluding Sparkle which we handle separately)
find "$BUNDLE/Contents/Frameworks" -type f -perm +111 \
    ! -path "*/Sparkle.framework/*" 2>/dev/null | while read -r bin; do
    codesign --force --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$SIGN_IDENTITY" \
        --timestamp \
        "$bin" 2>/dev/null
done

if [[ -d "$BUNDLE/Contents/Frameworks/Sparkle.framework" ]]; then
    echo "▸ Signing Sparkle.framework..."
    find "$BUNDLE/Contents/Frameworks/Sparkle.framework" -type f -perm +111 | while read -r bin; do
        codesign --force --options runtime \
            --sign "$SIGN_IDENTITY" \
            --timestamp \
            "$bin" 2>/dev/null
    done

    find "$BUNDLE/Contents/Frameworks/Sparkle.framework" \
        \( -name "*.xpc" -o -name "*.app" \) -type d -prune | while read -r nested; do
        codesign --force --options runtime \
            --sign "$SIGN_IDENTITY" \
            --timestamp \
            "$nested" 2>/dev/null
    done

    codesign --force --options runtime \
        --sign "$SIGN_IDENTITY" \
        --timestamp \
        "$BUNDLE/Contents/Frameworks/Sparkle.framework" 2>/dev/null
    echo "  ✓ Sparkle signed"
fi

# Sign the main executable
codesign --force --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$SIGN_IDENTITY" \
    --timestamp \
    "$BUNDLE/Contents/MacOS/vvrite" 2>/dev/null

# Sign the .app bundle itself
codesign --force --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$SIGN_IDENTITY" \
    --timestamp \
    "$BUNDLE" 2>/dev/null

echo "  ✓ Signing complete"

# ── Step 3: Verify signature ──────────────────────────────────
echo "▸ Verifying signature..."
codesign --verify --deep --strict "$BUNDLE" 2>&1 || \
    echo "  ⚠ Signature verification warning (expected for ad-hoc sign)"
echo "  ✓ Verification done"

# ── Step 4: Create distribution DMG ─────────────────────────
echo "▸ Creating DMG..."
rm -f "$DMG"
DMG_STAGE=$(mktemp -d)
cp -R "$BUNDLE" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Applications"
hdiutil create -volname "vvrite" -srcfolder "$DMG_STAGE" \
    -ov -format UDZO "$DMG"
rm -rf "$DMG_STAGE"

echo "  ✓ DMG ready: $DMG"

echo ""
echo "✓ Done! $DMG is ready for local testing."
echo "  Open it with: open $DMG"
