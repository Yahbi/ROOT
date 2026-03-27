#!/bin/bash
# Install ROOT as a macOS LaunchAgent (runs at login, restarts on crash)

set -e

PLIST_NAME="com.root.ai.plist"
PLIST_SRC="$(cd "$(dirname "$0")/.." && pwd)/${PLIST_NAME}"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}"
LOG_DIR="$(cd "$(dirname "$0")/.." && pwd)/logs"

echo "=== ROOT Service Installer ==="

# Create logs directory
mkdir -p "$LOG_DIR"
echo "Created logs directory: $LOG_DIR"

# Copy plist to LaunchAgents
cp "$PLIST_SRC" "$PLIST_DST"
echo "Installed plist: $PLIST_DST"

# Load the service
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "Service loaded and started"

echo ""
echo "=== ROOT is now running as a system service ==="
echo "  Status:  launchctl list | grep com.root.ai"
echo "  Logs:    tail -f $LOG_DIR/root-stdout.log"
echo "  Stop:    launchctl unload $PLIST_DST"
echo "  Start:   launchctl load $PLIST_DST"
echo "  Remove:  launchctl unload $PLIST_DST && rm $PLIST_DST"
