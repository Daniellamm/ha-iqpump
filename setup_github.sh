#!/usr/bin/env bash
# One-shot script: creates the GitHub repo and pushes ha-iqpump
# Run from inside the ha-iqpump directory:
#   cd /path/to/ha-iqpump && bash setup_github.sh

set -e

REPO_NAME="ha-iqpump"
GITHUB_USER="Daniellamm"

echo "==> Initialising git..."
git init
git add .
git commit -m "Initial release: Jandy iQPUMP01 Home Assistant integration

Custom component for the Jandy iQPUMP01 (i2d device type).
Supports pump on/off, RPM, watts, speed sensors, and target RPM control.
Auth uses AWS SigV4 with Cognito credentials — works for both owners and shared users.
Ready for installation via HACS custom repository."

echo "==> Creating public GitHub repo..."
gh repo create "$GITHUB_USER/$REPO_NAME" \
  --public \
  --description "Home Assistant custom integration for the Jandy iQPUMP01 pool pump (i2d device type)" \
  --source . \
  --remote origin \
  --push

echo "==> Tagging v1.0.0 release (required by HACS)..."
git tag v1.0.0
git push origin v1.0.0

echo "==> Creating GitHub release..."
gh release create v1.0.0 \
  --title "v1.0.0 — Initial release" \
  --notes "First public release of the Jandy iQPUMP01 Home Assistant integration.

**Features**
- Pump on/off switch
- RPM, power (watts), and speed preset sensors
- Target RPM number entity (slider, 600–3450 RPM)
- AWS SigV4 authentication — works for owners and shared users
- Auto token refresh — no manual re-auth needed
- Entities go unavailable gracefully when cloud is unreachable

**Installation**
Add this repo as a custom repository in HACS (category: Integration), then search for iQPUMP."

echo ""
echo "✅ Done! Your integration is live at:"
echo "   https://github.com/$GITHUB_USER/$REPO_NAME"
echo ""
echo "To add to HACS on your Home Assistant instance:"
echo "  HACS → Integrations → ⋮ → Custom repositories"
echo "  URL: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "  Category: Integration"
