#!/bin/bash
# Package the Appian Deployment MCP Server into a distributable tarball.
#
# Usage: ./package.sh
# Output: appian-deployment-mcp.tar.gz

set -e

PACKAGE_NAME="appian-deployment-mcp"
OUTPUT_FILE="${PACKAGE_NAME}.tar.gz"

echo "Packaging ${PACKAGE_NAME}..."

# Create a temp directory for the clean package
TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="${TEMP_DIR}/${PACKAGE_NAME}"
mkdir -p "$PACKAGE_DIR"

# Copy only the files users need
cp -r src "$PACKAGE_DIR/"
cp pyproject.toml "$PACKAGE_DIR/"
cp uv.lock "$PACKAGE_DIR/"
cp README.md "$PACKAGE_DIR/"
cp setup.sh "$PACKAGE_DIR/"
cp .gitignore "$PACKAGE_DIR/"

# Copy tests (optional, but useful for verification)
cp -r tests "$PACKAGE_DIR/"

# Remove any __pycache__ directories
find "$PACKAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Create the tarball
tar -czf "$OUTPUT_FILE" -C "$TEMP_DIR" "$PACKAGE_NAME"

# Cleanup
rm -rf "$TEMP_DIR"

# Report
SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo ""
echo "✓ Created ${OUTPUT_FILE} (${SIZE})"
echo ""
echo "Users can install with:"
echo "  tar -xzf ${OUTPUT_FILE}"
echo "  cd ${PACKAGE_NAME}"
echo "  ./setup.sh"
