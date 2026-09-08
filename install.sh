#!/usr/bin/env bash
set -euo pipefail

src="$(cd "$(dirname "$0")" && pwd)/com_misza_herd"
dest="${XDG_DATA_HOME:-$HOME/.var/app/com.core447.StreamController/data}/plugins/com_misza_herd"

if [[ ! -d $src ]]; then
  echo "missing plugin tree: $src" >&2
  exit 1
fi

mkdir -p "$(dirname "$dest")"
rsync -a --delete --exclude __pycache__ --exclude '*.pyc' "$src/" "$dest/"
echo "installed $dest"

if command -v gdbus >/dev/null && gdbus call --session \
  --dest com.core447.StreamController \
  --object-path /com/core447/StreamController \
  --method org.gtk.Actions.Activate "quit" "[]" "@a{sv} {}" >/dev/null 2>&1; then
  sleep 2
fi
if command -v streamcontroller >/dev/null; then
  setsid streamcontroller >/dev/null 2>&1 < /dev/null &
  echo "restarted StreamController"
fi
