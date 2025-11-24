#!/usr/bin/env python3
"""
Fetch and print instrument tokens for GOLDBEES/SILVERBEES on NSE/BSE.

Usage:
  export KITE_API_KEY=...
  export KITE_API_SECRET=...
  export KITE_ACCESS_TOKEN=...
  python3 scripts/print_instrument_tokens.py
"""

import os
import sys

from kiteconnect import KiteConnect  # type: ignore


def main():
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")
    if not api_key or not access_token:
        print("Set KITE_API_KEY and KITE_ACCESS_TOKEN environment variables.", file=sys.stderr)
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    wanted = {
        ("GOLDBEES", "NSE"),
        ("GOLDBEES", "BSE"),
        ("SILVERBEES", "NSE"),
        ("SILVERBEES", "BSE"),
    }
    try:
        instruments = kite.instruments()
    except Exception as e:
        print(f"Failed to fetch instruments: {e}", file=sys.stderr)
        sys.exit(1)

    found = []
    for r in instruments:
        key = (r.get("tradingsymbol"), r.get("exchange"))
        if key in wanted:
            found.append((r["tradingsymbol"], r["exchange"], r["instrument_token"]))

    if not found:
        print("No matching instruments found; check your access token/market availability.", file=sys.stderr)
        sys.exit(1)

    print("Instrument tokens:")
    for sym, exch, tok in found:
        print(f"{sym} {exch} token={tok}")

    print("\nAdd these to config/config.yaml under broker.token_map, e.g.:")
    for sym, exch, tok in found:
        print(f'  "{tok}": {{symbol: "{sym}", exchange: "{exch}"}}')


if __name__ == "__main__":
    main()
