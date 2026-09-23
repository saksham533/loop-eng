#!/usr/bin/env bash
for port in 4001 4002 4003; do
  pid=$(lsof -ti:$port 2>/dev/null || true)
  [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
done
echo "Stopped mocks."