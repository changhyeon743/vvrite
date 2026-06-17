#!/usr/bin/env bash
set -euo pipefail

SPARKLE_VERSION="${SPARKLE_VERSION:-2.9.2}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="${SPARKLE_VENDOR_DIR:-$ROOT_DIR/vendor/Sparkle}"
ARCHIVE_URL="https://github.com/sparkle-project/Sparkle/releases/download/${SPARKLE_VERSION}/Sparkle-${SPARKLE_VERSION}.tar.xz"

if [[ -d "$VENDOR_DIR/Sparkle.framework" && -x "$VENDOR_DIR/bin/generate_appcast" ]]; then
    echo "  ✓ Sparkle ${SPARKLE_VERSION} already prepared"
    exit 0
fi

echo "▸ Downloading Sparkle ${SPARKLE_VERSION}..."
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/Sparkle.tar.xz"
mkdir -p "$VENDOR_DIR"
tar -xJf "$TMP_DIR/Sparkle.tar.xz" -C "$TMP_DIR"

rm -rf "$VENDOR_DIR/Sparkle.framework" "$VENDOR_DIR/bin"
ditto "$TMP_DIR/Sparkle.framework" "$VENDOR_DIR/Sparkle.framework"
ditto "$TMP_DIR/bin" "$VENDOR_DIR/bin"

echo "  ✓ Sparkle prepared at $VENDOR_DIR"
