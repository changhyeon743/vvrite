#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ── Configuration ──────────────────────────────────────────────
IDENTITY="Developer ID Application: Saturn Studio (449B2G47F7)"
BUNDLE="dist/vvrite.app"
ENTITLEMENTS="entitlements.plist"
NOTARY_PROFILE="notarytool-profile"
ZIP="dist/vvrite.zip"
DMG="dist/vvrite.dmg"
SPARKLE_ENABLED="${SPARKLE_ENABLED:-1}"
SPARKLE_VENDOR_DIR="${SPARKLE_VENDOR_DIR:-$ROOT_DIR/vendor/Sparkle}"
SPARKLE_FRAMEWORK="$SPARKLE_VENDOR_DIR/Sparkle.framework"
SPARKLE_KEY_ACCOUNT="${SPARKLE_KEY_ACCOUNT:-vvrite-shaircast}"
# Public EdDSA key for the vvrite-shaircast signing key (verify with
# `vendor/Sparkle/bin/generate_keys --account vvrite-shaircast -p`). Defaulted
# here so release builds work without exporting it each time; update this if the
# signing key is ever rotated.
export SPARKLE_PUBLIC_ED_KEY="${SPARKLE_PUBLIC_ED_KEY:-nOeh/Q16IsXOKE7vczErR7PTe87iwBSZu3AZ0GXw6A4=}"

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
    if [[ -z "${SPARKLE_PUBLIC_ED_KEY:-}" ]]; then
        cat >&2 <<EOF
Missing SPARKLE_PUBLIC_ED_KEY.

Generate or look up the Sparkle public key with:
  ./scripts/prepare_sparkle.sh
  vendor/Sparkle/bin/generate_keys --account ${SPARKLE_KEY_ACCOUNT}

Then export the printed SUPublicEDKey value before building:
  export SPARKLE_PUBLIC_ED_KEY="..."

Set SPARKLE_ENABLED=0 only for a local build without Sparkle.
EOF
        exit 1
    fi

    echo "▸ Preparing Sparkle..."
    "$ROOT_DIR/scripts/prepare_sparkle.sh"
fi

# ── Step 0.5: Backward-compatible metallib ────────────────────
# mlx-metal ships per-macOS-version wheels. A metallib built for macOS 26
# (MSL 4.0) won't load on macOS 15. Swap in the macOS 15 wheel's metallib
# so the resulting .app runs on macOS 15+.
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

# ── Step 2: Sign all binaries inside the bundle ────────────────
echo "▸ Signing embedded binaries..."

# Sign .so and .dylib files first (innermost → outermost)
find "$BUNDLE" -type f \( -name "*.so" -o -name "*.dylib" \) | while read -r lib; do
    codesign --force --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" \
        --timestamp \
        "$lib"
done

# Sign embedded frameworks
find "$BUNDLE/Contents/Frameworks" -type f -perm +111 \
    ! -path "*/Sparkle.framework/*" 2>/dev/null | while read -r bin; do
    codesign --force --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" \
        --timestamp \
        "$bin"
done

if [[ -d "$BUNDLE/Contents/Frameworks/Sparkle.framework" ]]; then
    echo "▸ Signing Sparkle.framework..."

    find "$BUNDLE/Contents/Frameworks/Sparkle.framework" -type f -perm +111 | while read -r bin; do
        codesign --force --options runtime \
            --sign "$IDENTITY" \
            --timestamp \
            "$bin"
    done

    find "$BUNDLE/Contents/Frameworks/Sparkle.framework" \
        \( -name "*.xpc" -o -name "*.app" \) -type d -prune | while read -r nested; do
        codesign --force --options runtime \
            --sign "$IDENTITY" \
            --timestamp \
            "$nested"
    done

    codesign --force --options runtime \
        --sign "$IDENTITY" \
        --timestamp \
        "$BUNDLE/Contents/Frameworks/Sparkle.framework"

    echo "  ✓ Sparkle signed"
fi

# Sign the main executable
codesign --force --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$IDENTITY" \
    --timestamp \
    "$BUNDLE/Contents/MacOS/vvrite"

# Sign the .app bundle itself
codesign --force --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$IDENTITY" \
    --timestamp \
    "$BUNDLE"

echo "  ✓ Signing complete"

# ── Step 3: Verify signature ──────────────────────────────────
echo "▸ Verifying signature..."
codesign --verify --deep --strict "$BUNDLE"
echo "  ✓ Signature valid"

# ── Step 4: Notarize ──────────────────────────────────────────
echo "▸ Creating zip for notarization..."
ditto -c -k --keepParent "$BUNDLE" "$ZIP"

echo "▸ Submitting for notarization (this may take a few minutes)..."
xcrun notarytool submit "$ZIP" \
    --keychain-profile "$NOTARY_PROFILE" \
    --wait

# ── Step 5: Staple ────────────────────────────────────────────
echo "▸ Stapling notarization ticket..."
xcrun stapler staple "$BUNDLE"
echo "  ✓ Staple complete"

# ── Step 6: Final verification ────────────────────────────────
echo "▸ Final Gatekeeper check..."
spctl --assess --type exec --verbose "$BUNDLE"

# ── Step 7: Create distribution DMG ─────────────────────────
echo "▸ Creating DMG..."
rm -f "$DMG"
DMG_STAGE=$(mktemp -d)
cp -R "$BUNDLE" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Applications"
hdiutil create -volname "vvrite" -srcfolder "$DMG_STAGE" \
    -ov -format UDZO "$DMG"
rm -rf "$DMG_STAGE"

echo "▸ Signing DMG..."
codesign --force --sign "$IDENTITY" --timestamp "$DMG"

echo "▸ Notarizing DMG..."
xcrun notarytool submit "$DMG" \
    --keychain-profile "$NOTARY_PROFILE" \
    --wait

echo "▸ Stapling DMG..."
xcrun stapler staple "$DMG"
echo "  ✓ DMG ready: $DMG"

if [[ "${SPARKLE_GENERATE_APPCAST:-0}" == "1" ]]; then
    echo "▸ Generating Sparkle appcast..."
    APP_VERSION=$(python - <<'PY'
from vvrite import __version__
print(__version__)
PY
)
    UPDATE_DIR="${SPARKLE_UPDATE_DIR:-dist/sparkle-updates}"
    UPDATE_DMG="$UPDATE_DIR/vvrite-${APP_VERSION}.dmg"
    mkdir -p "$UPDATE_DIR"
    ditto "$DMG" "$UPDATE_DMG"

    APPCAST_ARGS=()
    if [[ -n "${SPARKLE_DOWNLOAD_URL_PREFIX:-}" ]]; then
        APPCAST_ARGS+=(--download-url-prefix "$SPARKLE_DOWNLOAD_URL_PREFIX")
    fi
    if [[ -n "${SPARKLE_RELEASE_NOTES_URL_PREFIX:-}" ]]; then
        APPCAST_ARGS+=(--release-notes-url-prefix "$SPARKLE_RELEASE_NOTES_URL_PREFIX")
    fi

    if [[ -n "${SPARKLE_PRIVATE_ED_KEY:-}" ]]; then
        echo "$SPARKLE_PRIVATE_ED_KEY" | \
            "$SPARKLE_VENDOR_DIR/bin/generate_appcast" \
                ${APPCAST_ARGS[@]+"${APPCAST_ARGS[@]}"} --ed-key-file - "$UPDATE_DIR"
    elif [[ -n "${SPARKLE_ED_KEY_FILE:-}" ]]; then
        "$SPARKLE_VENDOR_DIR/bin/generate_appcast" \
            ${APPCAST_ARGS[@]+"${APPCAST_ARGS[@]}"} --ed-key-file "$SPARKLE_ED_KEY_FILE" "$UPDATE_DIR"
    else
        "$SPARKLE_VENDOR_DIR/bin/generate_appcast" \
            ${APPCAST_ARGS[@]+"${APPCAST_ARGS[@]}"} --account "$SPARKLE_KEY_ACCOUNT" "$UPDATE_DIR"
    fi

    echo "  ✓ Appcast ready: $UPDATE_DIR/appcast.xml"
fi

echo ""
echo "✓ Done! $DMG is signed, notarized, and ready for distribution."
