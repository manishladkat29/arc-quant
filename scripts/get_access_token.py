#!/usr/bin/env python3
"""
Helper script to exchange a Zerodha request_token for an access_token.

Usage:
  export KITE_API_KEY=...
  export KITE_API_SECRET=...
  python3 scripts/get_access_token.py --request-token <REQUEST_TOKEN_FROM_LOGIN>
"""

import argparse
import os
import sys

from kiteconnect import KiteConnect  # type: ignore


def main():
    parser = argparse.ArgumentParser(description="Exchange Zerodha request_token for access_token")
    parser.add_argument("--request-token", required=True, help="request_token obtained after login redirect")
    args = parser.parse_args()

    api_key = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")
    if not api_key or not api_secret:
        print("Set KITE_API_KEY and KITE_API_SECRET environment variables.", file=sys.stderr)
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    try:
        data = kite.generate_session(args.request_token, api_secret=api_secret)
    except Exception as e:
        print(f"Failed to generate session: {e}", file=sys.stderr)
        sys.exit(1)

    access_token = data.get("access_token")
    print("access_token:", access_token)
    print("\nExport this for your run:")
    print(f"export KITE_ACCESS_TOKEN={access_token}")


if __name__ == "__main__":
    main()
