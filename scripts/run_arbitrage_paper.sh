#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/run_arbitrage_paper.sh
#
# Preconditions:
#   - Python 3 and venv available
#   - KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN set (for live ticks)
#   - broker.token_map populated in config/config.yaml with NSE/BSE tokens for GOLDBEES/SILVERBEES
#
# This runs the main engine in paper mode with the arbitrage strategy enabled.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$ROOT_DIR/requirements.txt" kiteconnect >/dev/null

export PYTHONPATH="$ROOT_DIR"

exec python3 -m main --mode paper --config "$ROOT_DIR/config/config.yaml"
