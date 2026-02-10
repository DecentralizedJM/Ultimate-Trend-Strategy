"""
Symbol Fetcher
==============

Fetches all available perpetual futures symbols from Mudrex API.
Uses the Mudrex trade API with pagination.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

MUDREX_ASSETS_URL = "https://trade.mudrex.com/fapi/v1/futures"


def fetch_mudrex_symbols(api_secret: str) -> List[str]:
    """
    Fetch all available USDT futures symbols from Mudrex API.

    Args:
        api_secret: Mudrex API secret for X-Authentication header

    Returns:
        Sorted list of symbol names (e.g., ["BTCUSDT", "ETHUSDT", ...])
    """
    import urllib.request
    import json

    symbols = []
    offset = 0
    limit = 100

    try:
        while True:
            url = f"{MUDREX_ASSETS_URL}?sort=popularity&order=asc&offset={offset}&limit={limit}"
            req = urllib.request.Request(
                url,
                headers={
                    "X-Authentication": api_secret,
                    "User-Agent": "UltimateTrendBot/1.0",
                },
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            if not data.get("success"):
                logger.error(f"Mudrex API error: {data}")
                break

            assets = data.get("data", [])
            if not assets:
                break

            for asset in assets:
                symbol = asset.get("symbol", "")
                if symbol and symbol.endswith("USDT"):
                    symbols.append(symbol)

            if len(assets) < limit:
                break
            offset += limit

        symbols = sorted(set(symbols))
        logger.info(f"✅ Fetched {len(symbols)} symbols from Mudrex")

    except Exception as e:
        logger.error(f"Failed to fetch Mudrex symbols: {e}")

    return symbols
