#!/bin/bash
# Build signed and notarized macOS installer package
# Usage: ./build-pkg.sh <version>
#
# Required environment variables for signing:
#   APPLE_CERTIFICATE_APPLICATION - base64 encoded .p12
#   APPLE_CERTIFICATE_INSTALLER - base64 encoded .p12
#   APPLE_CERTIFICATE_PASSWORD - .p12 password
#   APPLE_ID - Apple ID email
#   APPLE_TEAM_ID - 10-char team ID
#   APPLE_APP_PASSWORD - app-specific password
#
# Update these for your plugin:
PLUGIN_NAME="AudioPlugin"
BUNDLE_ID="com.example.audioplugin"
# Update these with your Apple Developer credentials:
APP_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"
PKG_IDENTITY="Developer ID Installer: Your Name (TEAM_ID)"

set -e

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/${PLUGIN_NAME}_artefacts/Release"
PKG_ROOT="$PROJECT_ROOT/build/pkg-root"
PKG_OUT="$PROJECT_ROOT/build/installer"

VST3_SRC="$BUILD_DIR/VST3/$PLUGIN_NAME.vst3"
AU_SRC="$BUILD_DIR/AU/$PLUGIN_NAME.component"

echo "=== Building $PLUGIN_NAME $VERSION macOS Installer ==="

# Verify builds exist
if [ ! -d "$VST3_SRC" ] || [ ! -d "$AU_SRC" ]; then
    echo "Error: Build artifacts not found. Run build first."
    echo "Expected: $VST3_SRC"
    echo "Expected: $AU_SRC"
    exit 1
fi

# Check for signing identity
if ! security find-identity -v -p codesigning | grep -q "$APP_IDENTITY"; then
    echo "Error: Signing identity not found: $APP_IDENTITY"
    echo "Available identities:"
    security find-identity -v -p codesigning
    exit 1
fi

# Clean and create package structure
rm -rf "$PKG_ROOT" "$PKG_OUT"
mkdir -p "$PKG_ROOT/Library/Audio/Plug-Ins/VST3"
mkdir -p "$PKG_ROOT/Library/Audio/Plug-Ins/Components"
mkdir -p "$PKG_OUT"

# Copy plugins
echo "Copying plugins..."
cp -R "$VST3_SRC" "$PKG_ROOT/Library/Audio/Plug-Ins/VST3/"
cp -R "$AU_SRC" "$PKG_ROOT/Library/Audio/Plug-Ins/Components/"

# Sign plugins
echo "Signing VST3..."
codesign --force --deep --sign "$APP_IDENTITY" \
    --options runtime \
    --timestamp \
    "$PKG_ROOT/Library/Audio/Plug-Ins/VST3/$PLUGIN_NAME.vst3"

echo "Signing AU..."
codesign --force --deep --sign "$APP_IDENTITY" \
    --options runtime \
    --timestamp \
    "$PKG_ROOT/Library/Audio/Plug-Ins/Components/$PLUGIN_NAME.component"

# Verify signatures
echo "Verifying signatures..."
codesign --verify --deep --strict "$PKG_ROOT/Library/Audio/Plug-Ins/VST3/$PLUGIN_NAME.vst3"
codesign --verify --deep --strict "$PKG_ROOT/Library/Audio/Plug-Ins/Components/$PLUGIN_NAME.component"

# Build component package
echo "Building package..."
pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "$BUNDLE_ID.pkg" \
    --version "$VERSION" \
    --install-location "/" \
    "$PKG_OUT/$PLUGIN_NAME-unsigned.pkg"

# Sign the package
echo "Signing package..."
productsign \
    --sign "$PKG_IDENTITY" \
    "$PKG_OUT/$PLUGIN_NAME-unsigned.pkg" \
    "$PKG_OUT/$PLUGIN_NAME-${VERSION}-macOS.pkg"

rm "$PKG_OUT/$PLUGIN_NAME-unsigned.pkg"

# Verify package signature
echo "Verifying package signature..."
pkgutil --check-signature "$PKG_OUT/$PLUGIN_NAME-${VERSION}-macOS.pkg"

# Notarize
echo "Submitting for notarization..."
xcrun notarytool submit "$PKG_OUT/$PLUGIN_NAME-${VERSION}-macOS.pkg" \
    --keychain-profile "notarytool-profile" \
    --wait

# Staple the ticket
echo "Stapling notarization ticket..."
xcrun stapler staple "$PKG_OUT/$PLUGIN_NAME-${VERSION}-macOS.pkg"

# Verify staple
xcrun stapler validate "$PKG_OUT/$PLUGIN_NAME-${VERSION}-macOS.pkg"

echo ""
echo "=== Done ==="
echo "Installer: $PKG_OUT/$PLUGIN_NAME-${VERSION}-macOS.pkg"
