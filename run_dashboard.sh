#!/usr/bin/env bash
cd "$(dirname "$0")"

# Free port 8000 if a previous server is still bound to it
lsof -ti:8000 | xargs -r kill -9 2>/dev/null

python3 -m http.server 8000 &
SERVER_PID=$!

sleep 1

open "http://127.0.0.1:8000/index.html?t=$RANDOM" 2>/dev/null || xdg-open "http://127.0.0.1:8000/index.html?t=$RANDOM"

wait $SERVER_PID
