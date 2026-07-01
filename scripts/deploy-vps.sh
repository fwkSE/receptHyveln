#!/usr/bin/env bash
set -euo pipefail

# Deploy the published container image to a VPS running docker compose.
#
#   cp deploy.config.example deploy.config   # edit values
#   VPS_DEPLOY=true ./scripts/deploy-vps.sh
#
# Override any setting via environment variables when calling the script.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${DEPLOY_CONFIG:-$ROOT_DIR/deploy.config}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$CONFIG_FILE"
fi

VPS_HOST="${VPS_HOST:-YOUR_VPS_IP_OR_HOSTNAME}"
VPS_USER="${VPS_USER:-YOUR_VPS_USER}"
VPS_PORT="${VPS_PORT:-22}"
VPS_SSH_KEY="${VPS_SSH_KEY:-$HOME/.ssh/YOUR_VPS_SSH_KEY}"
VPS_APP_DIR="${VPS_APP_DIR:-/opt/recept-hyveln}"
VPS_DEPLOY="${VPS_DEPLOY:-false}"

require_config() {
  local name="$1"
  local value="$2"

  if [[ "$value" == YOUR_* || -z "$value" ]]; then
    echo "Missing deploy config: $name" >&2
    exit 1
  fi
}

if [[ "$VPS_DEPLOY" != "true" ]]; then
  echo "Set VPS_DEPLOY=true in deploy.config when the remote host is ready." >&2
  exit 1
fi

require_config "VPS_HOST" "$VPS_HOST"
require_config "VPS_USER" "$VPS_USER"
require_config "VPS_SSH_KEY" "$VPS_SSH_KEY"

if [[ ! -r "$VPS_SSH_KEY" ]]; then
  echo "SSH key is not readable: $VPS_SSH_KEY" >&2
  exit 1
fi

SSH=(ssh -i "$VPS_SSH_KEY" -p "$VPS_PORT" -o BatchMode=yes)
REMOTE="${VPS_USER}@${VPS_HOST}"

echo "Deploying on $REMOTE:$VPS_APP_DIR ..."
"${SSH[@]}" "$REMOTE" "set -euo pipefail
  APP_DIR=\"$VPS_APP_DIR\"
  APP_DIR=\"\${APP_DIR/#\\~/$HOME}\"
  if [[ ! -d \"\$APP_DIR\" ]]; then
    echo \"Remote app directory not found: \$APP_DIR\" >&2
    exit 1
  fi
  cd \"\$APP_DIR\"
  if [[ ! -f docker-compose.yml ]]; then
    echo \"docker-compose.yml not found in \$APP_DIR\" >&2
    exit 1
  fi
  if [[ ! -f .env ]]; then
    echo \".env not found in \$APP_DIR — copy .env.production.example first\" >&2
    exit 1
  fi
  docker compose pull
  docker compose up -d --remove-orphans
  docker compose ps
"

echo "Deploy complete."
