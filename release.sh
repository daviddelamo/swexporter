#!/bin/bash
# ═══════════════════════════════════════════════════
# Release script for SWADE PDF Exporter Foundry Module
# Creates a zip archive and a GitHub release.
#
# Usage:
#   ./release.sh [version]
#   ./release.sh 1.0.0
#
# Requirements:
#   - gh (GitHub CLI) installed and authenticated
# ═══════════════════════════════════════════════════

set -euo pipefail

VERSION="${1:-$(jq -r .version foundry-module/module.json)}"
TAG="v${VERSION}"
ZIP_NAME="swade-pdf-exporter.zip"
BUILD_DIR=$(mktemp -d)

echo "📦 Building release ${TAG}..."

# Update version in module.json
jq --arg v "$VERSION" '.version = $v' foundry-module/module.json > "${BUILD_DIR}/module.json.tmp"
cp "${BUILD_DIR}/module.json.tmp" foundry-module/module.json
rm "${BUILD_DIR}/module.json.tmp"

# Build the zip with the correct internal folder structure
# Foundry expects: swade-pdf-exporter/module.json, swade-pdf-exporter/scripts/...
mkdir -p "${BUILD_DIR}/swade-pdf-exporter"
cp -r foundry-module/* "${BUILD_DIR}/swade-pdf-exporter/"

# Create zip
(cd "${BUILD_DIR}" && zip -r "${ZIP_NAME}" swade-pdf-exporter/)
cp "${BUILD_DIR}/${ZIP_NAME}" .

echo "✅ Created ${ZIP_NAME}"

# Commit version bump
git add foundry-module/module.json
git commit -m "chore: bump module version to ${VERSION}" --allow-empty
git tag -a "${TAG}" -m "Release ${TAG}"
git push origin main --tags

# Create GitHub release with the zip + module.json
echo "🚀 Creating GitHub release ${TAG}..."
gh release create "${TAG}" \
  "${ZIP_NAME}" \
  "foundry-module/module.json" \
  --title "SWADE PDF Exporter ${TAG}" \
  --notes "## SWADE PDF Character Exporter ${TAG}

### Installation in Foundry VTT
1. Go to **Add-on Modules → Install Module**
2. Paste this manifest URL:
   \`\`\`
   https://github.com/daviddelamo/swexporter/releases/latest/download/module.json
   \`\`\`
3. Click **Install**

### API Server
Deploy the API using Docker Compose or Coolify. See the [README](https://github.com/daviddelamo/swexporter) for details."

# Cleanup
rm -rf "${BUILD_DIR}" "${ZIP_NAME}"

echo "🎉 Release ${TAG} published!"
echo ""
echo "📋 Install URL for Foundry VTT:"
echo "   https://github.com/daviddelamo/swexporter/releases/latest/download/module.json"
