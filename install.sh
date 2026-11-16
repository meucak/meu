#!/usr/bin/env bash
set -euo pipefail

RAW_URL="${MEU_RAW_URL:-https://raw.githubusercontent.com/meucak/meu/main/meu.py}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[HATA] Python 3 bulunamadı. Lütfen önce python3 kurun (ör. sudo apt install python3)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
LOCAL_MEU="$SCRIPT_DIR/meu.py"

if [ -f "$LOCAL_MEU" ]; then
  python3 "$LOCAL_MEU" self-install
else
  TMP_MEU="$(mktemp /tmp/meu_install_XXXXXX.py)"
  trap 'rm -f "$TMP_MEU"' EXIT
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$RAW_URL" -o "$TMP_MEU"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP_MEU" "$RAW_URL"
  else
    python3 -c "import urllib.request; urllib.request.urlretrieve('$RAW_URL', '$TMP_MEU')"
  fi
  python3 "$TMP_MEU" self-install
fi
