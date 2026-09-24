#!/bin/sh
# Ser till att datakatalogen är skrivbar och kör sedan appen som PUID:PGID i stället för root.
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
DATA_DIR="${DATA_DIR:-/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown "$PUID:$PGID" "$DATA_DIR"
  # Filer från tidigare körningar kan ha annan ägare
  find "$DATA_DIR" -maxdepth 1 -name '*.json*' ! -user "$PUID" -exec chown "$PUID:$PGID" {} + 2>/dev/null || true
  if command -v setpriv >/dev/null 2>&1; then
    exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
  fi
  exec python -c 'import os, sys
os.setgroups([]); os.setgid(int(os.environ["PGID"])); os.setuid(int(os.environ["PUID"]))
os.execvp(sys.argv[1], sys.argv[1:])' "$@"
fi

exec "$@"
