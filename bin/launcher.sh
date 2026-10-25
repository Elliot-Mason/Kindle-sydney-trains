#!/bin/sh
# Sydney Trains Kindle Launcher for Jailbroken Kindle Paperwhite 1
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="/tmp/kindle-trains.pid"
PORT=5052

case "$1" in
  start)
    # Prevent Kindle from going into screensaver sleep
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
    
    # Kill any stale instance
    if [ -f "$PID_FILE" ]; then
      kill -9 $(cat "$PID_FILE") 2>/dev/null
      rm -f "$PID_FILE"
    fi
    
    # Start on-device Python server
    cd "$APP_DIR"
    python3 server.py --no-browser > /tmp/trains.log 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    # Clear screen and launch fullscreen browser to localhost
    eips -c 2>/dev/null
    lipc-set-prop com.lab126.appmgrd start "app://com.lab126.browser?view=http://127.0.0.1:${PORT}/kindle" 2>/dev/null
    ;;
  stop)
    if [ -f "$PID_FILE" ]; then
      kill -9 $(cat "$PID_FILE") 2>/dev/null
      rm -f "$PID_FILE"
    fi
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
    eips 2 2 "Sydney Trains Stopped (Sleep Restored)" 2>/dev/null
    ;;
esac
