#!/bin/bash
# ROOT — Oracle Cloud Free Tier Setup Script
# Supports Oracle Linux 9 (dnf) and Ubuntu 22.04/24.04 (apt)
#
# Free tier specs: 4 ARM cores, 24GB RAM, 200GB boot volume
# That's enough for ROOT + Ollama with 8B models running 24/7
#
# Usage:
#   Oracle Linux: scp -r ~/Desktop/ROOT opc@<IP>:~/ROOT && ssh opc@<IP> bash ~/ROOT/deploy/oracle-setup.sh
#   Ubuntu:       scp -r ~/Desktop/ROOT ubuntu@<IP>:~/ROOT && ssh ubuntu@<IP> bash ~/ROOT/deploy/oracle-setup.sh

set -euo pipefail

echo "============================================"
echo "  ROOT v1.0.0 — Oracle Cloud Setup"
echo "============================================"

# Detect OS
if [ -f /etc/oracle-release ] || grep -qi "oracle" /etc/os-release 2>/dev/null; then
    OS_TYPE="oracle"
    PKG_MGR="dnf"
    echo "  Detected: Oracle Linux"
elif [ -f /etc/lsb-release ] || grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    OS_TYPE="ubuntu"
    PKG_MGR="apt-get"
    echo "  Detected: Ubuntu"
else
    echo "  WARNING: Unknown OS, attempting dnf first, fallback to apt"
    if command -v dnf &>/dev/null; then
        OS_TYPE="oracle"
        PKG_MGR="dnf"
    else
        OS_TYPE="ubuntu"
        PKG_MGR="apt-get"
    fi
fi

# 1. System updates + Docker install
echo "[1/9] Updating system and installing dependencies..."
if [ "$OS_TYPE" = "oracle" ]; then
    sudo dnf update -y -q
    sudo dnf install -y -q git curl sqlite python3 python3-pip cronie

    # Docker CE on Oracle Linux (dnf)
    sudo dnf install -y -q dnf-utils
    sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    sudo dnf install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Firewall via firewalld (Oracle Linux default)
    echo "[3/9] Configuring firewall (firewalld)..."
    sudo systemctl enable --now firewalld 2>/dev/null || true
    sudo firewall-cmd --permanent --add-port=22/tcp 2>/dev/null || true
    sudo firewall-cmd --permanent --add-port=9000/tcp
    sudo firewall-cmd --reload
    echo "  Firewall: SSH + port 9000 open"
else
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io docker-compose-v2 git curl sqlite3 ufw python3 python3-pip

    # Firewall via ufw (Ubuntu default)
    echo "[3/9] Configuring firewall (ufw)..."
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow 22/tcp    # SSH
    sudo ufw allow 9000/tcp  # ROOT dashboard
    sudo ufw --force enable
    echo "  Firewall: SSH + port 9000 only"
fi

# 2. Docker setup
echo "[2/9] Configuring Docker..."
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# 4. Check ROOT directory
echo "[4/9] Setting up ROOT..."
cd ~
if [ ! -d "ROOT" ]; then
    echo "ERROR: ~/ROOT not found."
    echo "  Copy from your Mac: scp -r ~/Desktop/ROOT $USER@$(hostname -I | awk '{print $1}'):~/ROOT"
    exit 1
fi
cd ROOT

# 5. Create .env if missing
if [ ! -f ".env" ]; then
    echo "[5/9] Creating .env..."
    # Generate a random API key
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env << ENVEOF
# ROOT Configuration — Oracle Cloud
ROOT_HOST=0.0.0.0
ROOT_PORT=9000
ROOT_OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://ollama:11434

# Security — auto-generated API key
ROOT_API_KEY=${API_KEY}

# Free LLM providers (get free API keys)
# Groq: https://console.groq.com (free 30 RPM)
GROQ_API_KEY=

# Optional: paid LLM providers (fallback for complex tasks)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=

# Optional: paper trading (https://app.alpaca.markets)
ALPACA_API_KEY=
ALPACA_API_SECRET=

# Optional: notification services
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
ENVEOF
    echo "  .env created with auto-generated ROOT_API_KEY"
    echo "  API Key: ${API_KEY}"
    echo "  Edit .env to add optional API keys: nano ~/ROOT/.env"
fi

# 6. Install systemd service for auto-restart on reboot
echo "[6/9] Installing systemd service..."
sudo cp deploy/root.service /etc/systemd/system/root.service
# Fix WorkingDirectory to match actual path
sudo sed -i "s|/home/ubuntu/ROOT|$(pwd)|g" /etc/systemd/system/root.service
sudo sed -i "s|/home/opc/ROOT|$(pwd)|g" /etc/systemd/system/root.service
sudo systemctl daemon-reload
sudo systemctl enable root.service
echo "  ROOT will auto-start on reboot"

# 7. Setup daily backups (3am)
echo "[7/9] Configuring daily backups..."
chmod +x deploy/backup.sh
# Fix paths in backup script
sed -i "s|/home/ubuntu/ROOT|$(cd ~ && pwd)/ROOT|g" deploy/backup.sh
sed -i "s|/home/opc/ROOT|$(cd ~ && pwd)/ROOT|g" deploy/backup.sh
mkdir -p ~/ROOT/backups
# Ensure cron is running
if [ "$OS_TYPE" = "oracle" ]; then
    sudo systemctl enable --now crond 2>/dev/null || true
fi
(crontab -l 2>/dev/null | grep -v "backup.sh" ; echo "0 3 * * * $(pwd)/deploy/backup.sh >> $(pwd)/backups/backup.log 2>&1") | crontab -
echo "  Daily backups at 3am → ~/ROOT/backups/"

# 8. Start services
echo "[8/9] Starting ROOT + Ollama..."
docker compose up -d

# 9. Wait for health
echo "[9/9] Waiting for ROOT to start..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:9000/api/health > /dev/null 2>&1; then
        echo "  ROOT is ALIVE!"
        break
    fi
    sleep 2
done

PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "<your-public-ip>")
API_KEY_DISPLAY=$(grep ROOT_API_KEY .env | head -1 | cut -d= -f2)

echo ""
echo "============================================"
echo "  ROOT v1.0.0 — DEPLOYED AND RUNNING"
echo "============================================"
echo ""
echo "  Dashboard: http://${PUBLIC_IP}:9000"
echo "  Health:    http://${PUBLIC_IP}:9000/api/health"
echo "  API Key:   ${API_KEY_DISPLAY}"
echo "  Docs:      http://${PUBLIC_IP}:9000/docs"
echo ""
echo "  Ollama models downloading in background (5-10 min)..."
echo "  Monitor:   docker logs -f root-ollama-pull"
echo ""
echo "  System Features:"
echo "    - Auto-restart on reboot (systemd)"
echo "    - Daily backups at 3am (~/ROOT/backups/)"
echo "    - Log rotation (10MB max per service)"
echo "    - Firewall: SSH + port 9000 only"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f root-server   # Watch ROOT logs"
echo "    docker compose logs -f root-ollama   # Watch Ollama logs"
echo "    docker compose restart root-server   # Restart ROOT"
echo "    docker compose down                  # Stop everything"
echo "    docker compose up -d                 # Start everything"
echo "    sudo systemctl status root           # Check systemd status"
echo "    cat ~/ROOT/backups/backup.log        # Check backup status"
echo "============================================"
