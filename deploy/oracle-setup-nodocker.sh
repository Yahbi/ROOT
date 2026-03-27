#!/bin/bash
# ROOT — Oracle Cloud Setup (No Docker, direct Python)
# Works on 512MB RAM micro instances
# Oracle Linux 9, username: opc
#
# Usage: ssh -i ~/Downloads/ssh-key-*.key opc@<IP> bash ~/ROOT/deploy/oracle-setup-nodocker.sh

set -euo pipefail

echo "============================================"
echo "  ROOT v1.0.0 — Oracle Cloud (No Docker)"
echo "============================================"

# 1. Install Python deps (minimal, no full update)
echo "[1/6] Installing Python and dependencies..."
sudo dnf install -y python3.11 python3.11-pip python3.11-devel gcc sqlite cronie 2>&1 | tail -5
echo "  Python: $(python3.11 --version)"

# 2. Create virtualenv and install ROOT
echo "[2/6] Setting up Python environment..."
cd ~/ROOT
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Dependencies installed"

# 3. Create .env if missing
if [ ! -f ".env" ]; then
    echo "[3/6] Creating .env..."
    API_KEY=$(python3.11 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env << ENVEOF
# ROOT Configuration — Oracle Cloud
ROOT_HOST=0.0.0.0
ROOT_PORT=9000

# Security — auto-generated API key
ROOT_API_KEY=${API_KEY}

# Free LLM (get key at console.groq.com — free 30 RPM)
GROQ_API_KEY=

# Optional paid LLM providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=

# Optional: paper trading
ALPACA_API_KEY=
ALPACA_API_SECRET=
ENVEOF
    echo "  .env created — API Key: ${API_KEY}"
    echo "  Add your Groq key: nano ~/ROOT/.env"
fi

# 4. Firewall: allow port 9000
echo "[4/6] Opening firewall port 9000..."
sudo firewall-cmd --permanent --add-port=9000/tcp 2>/dev/null || true
sudo firewall-cmd --reload 2>/dev/null || true
echo "  Port 9000 open"

# 5. Create systemd service (runs uvicorn directly)
echo "[5/6] Installing systemd service..."
cat > /tmp/root-ai.service << SVCEOF
[Unit]
Description=ROOT AI Civilization
After=network.target

[Service]
Type=simple
User=opc
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=$(pwd)/.venv/bin/uvicorn backend.main:_fastapi_app --host 0.0.0.0 --port 9000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

sudo mv /tmp/root-ai.service /etc/systemd/system/root-ai.service
sudo systemctl daemon-reload
sudo systemctl enable root-ai.service
sudo systemctl start root-ai.service
echo "  ROOT service started"

# 6. Setup daily backups
echo "[6/6] Setting up daily backups..."
sudo systemctl enable --now crond 2>/dev/null || true
mkdir -p ~/ROOT/backups
chmod +x ~/ROOT/deploy/backup.sh
sed -i "s|/home/ubuntu/ROOT|$(pwd)|g" ~/ROOT/deploy/backup.sh
sed -i "s|/home/opc/ROOT|$(pwd)|g" ~/ROOT/deploy/backup.sh
(crontab -l 2>/dev/null | grep -v "backup.sh"; echo "0 3 * * * $(pwd)/deploy/backup.sh >> $(pwd)/backups/backup.log 2>&1") | crontab -
echo "  Daily backups at 3am"

# Wait for ROOT
echo ""
echo "Waiting for ROOT to start..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:9000/api/health > /dev/null 2>&1; then
        echo "ROOT is ALIVE!"
        break
    fi
    sleep 3
done

PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "146.235.221.41")

echo ""
echo "============================================"
echo "  ROOT — DEPLOYED AND RUNNING"
echo "============================================"
echo "  Dashboard: http://${PUBLIC_IP}:9000"
echo "  Health:    http://${PUBLIC_IP}:9000/api/health"
echo ""
echo "  Manage ROOT:"
echo "    sudo systemctl status root-ai    # Status"
echo "    sudo systemctl restart root-ai   # Restart"
echo "    sudo journalctl -u root-ai -f    # Live logs"
echo "    nano ~/ROOT/.env                 # Edit config"
echo "============================================"
