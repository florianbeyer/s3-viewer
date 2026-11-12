#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  rm -rf "$ROOT/.venv"
  UV="${UV:-}"
  if [[ -z "$UV" ]]; then
    if command -v uv >/dev/null 2>&1; then
      UV="$(command -v uv)"
    elif [[ -x "$HOME/.local/bin/uv" ]]; then
      UV="$HOME/.local/bin/uv"
    fi
  fi
  if [[ -n "$UV" && -x /usr/bin/python3.12 ]]; then
    "$UV" venv --python /usr/bin/python3.12 "$ROOT/.venv"
    "$UV" pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements.txt"
  elif /usr/bin/python3.14 -m venv "$ROOT/.venv" 2>/dev/null; then
    "$ROOT/.venv/bin/pip" install -U pip
    "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
  else
    python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install -U pip
    "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
  fi
fi

export AWS_EC2_METADATA_DISABLED=true
exec "$ROOT/.venv/bin/python" -m s3viewer "$@"
