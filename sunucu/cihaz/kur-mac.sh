#!/bin/sh
# Mac'e Tulpar cihaz ajanını kurar (LaunchAgent: oturum açılınca başlar). Anahtar ~/.tulpar-ajan/anahtar'a yazılır.
set -e
KLASOR="$HOME/.tulpar-ajan"; mkdir -p "$KLASOR"; chmod 700 "$KLASOR"
cp "$(dirname "$0")/mac-ajan.py" "$KLASOR/mac-ajan.py"
[ -f "$KLASOR/anahtar" ] || (python3 -c "import secrets;print(secrets.token_hex(24))" > "$KLASOR/anahtar"; chmod 600 "$KLASOR/anahtar")
PLIST="$HOME/Library/LaunchAgents/com.tulpar.ajan.plist"
cat > "$PLIST" <<P
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.tulpar.ajan</string>
<key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$KLASOR/mac-ajan.py</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/></dict></plist>
P
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Kuruldu. Mac Tailscale adresi:"; (tailscale ip -4 2>/dev/null || /Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4) | head -1
echo "Bu satırı Claude'a ver (HP'ye bağlamak için): MAC_ANAHTAR=$(cat "$KLASOR/anahtar")"

# Menü çubuğu uygulaması (rumps, ayrı sanal ortam) — oturum açılınca başlar
if [ ! -d "$KLASOR/venv" ]; then python3 -m venv "$KLASOR/venv"; fi
"$KLASOR/venv/bin/pip" install -q rumps
cp "$(dirname "$0")/mac-menu.py" "$KLASOR/mac-menu.py"
MP="$HOME/Library/LaunchAgents/com.tulpar.menu.plist"
cat > "$MP" <<P
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.tulpar.menu</string>
<key>ProgramArguments</key><array><string>$KLASOR/venv/bin/python</string><string>$KLASOR/mac-menu.py</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/></dict></plist>
P
launchctl unload "$MP" 2>/dev/null || true
launchctl load "$MP"
echo "Menü çubuğu uygulaması kuruldu."
