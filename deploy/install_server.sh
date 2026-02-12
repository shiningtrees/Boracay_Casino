#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash deploy/install_server.sh <REPO_URL> [APP_DIR] [BRANCH]
# Example:
#   bash deploy/install_server.sh https://github.com/you/Boracay_Casino.git /opt/boracay-casino main

REPO_URL="${1:-}"
APP_DIR="${2:-/opt/boracay-casino}"
BRANCH="${3:-main}"
SERVICE_NAME="boracay-casino"

if [[ -z "$REPO_URL" ]]; then
  echo "ERROR: REPO_URL is required."
  echo "Usage: bash deploy/install_server.sh <REPO_URL> [APP_DIR] [BRANCH]"
  exit 1
fi

echo "[1/8] Install Docker + Compose plugin"
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" || true

echo "[2/8] Prepare app directory: $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"

echo "[3/8] Clone or update repository"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "[4/8] Prepare runtime directories"
mkdir -p "$APP_DIR/logs" "$APP_DIR/data" "$APP_DIR/backups"

echo "[5/8] Prepare .env file"
if [[ ! -f "$APP_DIR/.env" ]]; then
  if [[ -f "$APP_DIR/.env.example" ]]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo "Created $APP_DIR/.env from .env.example"
  else
    touch "$APP_DIR/.env"
    echo "Created empty $APP_DIR/.env"
  fi
fi

echo "[6/8] Register systemd service"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=Boracay Casino Docker Compose Service
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=${APP_DIR}
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

echo "[7/8] Enable and start service"
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"

echo "[8/8] Done. Current status:"
sudo systemctl --no-pager status "${SERVICE_NAME}" || true
echo ""
echo "Next steps:"
echo "1) Fill ${APP_DIR}/.env with real keys/tokens."
echo "2) Restart service: sudo systemctl restart ${SERVICE_NAME}"
echo "3) View logs: docker compose -f ${APP_DIR}/docker-compose.yml logs -f --tail=200 casino"
