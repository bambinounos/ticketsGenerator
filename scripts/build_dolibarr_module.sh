#!/usr/bin/env bash
# build_dolibarr_module.sh - Generate a zip of the Dolibarr module ready for installation
#
# Usage:
#   ./scripts/build_dolibarr_module.sh
#
# Output:
#   dist/module_raffles-<version>.zip
#
# The zip contains the 'raffles/' folder at its root, which is the format
# Dolibarr expects when installing a module from a zip file
# (Admin > Modules > Deploy external module).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODULE_SRC="$ROOT_DIR/dolibarr_module/raffles"
DIST_DIR="$ROOT_DIR/dist"

# Read version from module descriptor
VERSION=$(grep -oP "\\\$this->version\s*=\s*'\K[0-9]+\.[0-9]+\.[0-9]+" \
    "$MODULE_SRC/core/modules/modRaffles.class.php" | head -1)

if [[ -z "$VERSION" ]]; then
    echo "Error: Could not read version from modRaffles.class.php"
    exit 1
fi

ZIP_NAME="module_raffles-${VERSION}.zip"

# Prepare dist directory
mkdir -p "$DIST_DIR"

# Build zip from the dolibarr_module directory so the zip root contains 'raffles/'
cd "$ROOT_DIR/dolibarr_module"
zip -r "$DIST_DIR/$ZIP_NAME" raffles/ \
    -x "raffles/__pycache__/*" \
    -x "raffles/.DS_Store" \
    -x "*/.DS_Store"

echo ""
echo "Module built successfully:"
echo "  File:    $DIST_DIR/$ZIP_NAME"
echo "  Version: $VERSION"
echo "  Size:    $(du -h "$DIST_DIR/$ZIP_NAME" | cut -f1)"
echo ""
echo "Install in Dolibarr: Admin > Modules > Deploy external module > Upload zip"
