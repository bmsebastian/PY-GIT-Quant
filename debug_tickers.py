# debug_tickers.py
import time
from state_bus import STATE

print("=" * 60)
print("Market Data Ticker Debug")
print("=" * 60)

# Wait for system to be ready
time.sleep(2)

# Get market data bus from somewhere - we need to access it
# Let's check STATE first
print(f"\nSTATE.prices: {dict(list(STATE.prices.items())[:5])}")
print(f"STATE.symbols_subscribed: {list(STATE.symbols_subscribed)[:5]}")

# Now let's manually test one ticker
from ib_client import IBClient
from market_data import MarketDataBus

print("\n--- Testing TSLA Ticker ---")
ibc = IBClient()
ib = ibc.connect()

print("Creating MarketDataBus...")
mdb = MarketDataBus(ib)

contract = ibc.stock("TSLA")
print(f"Contract: {contract}")

print("\nSubscribing to TSLA...")
mdb.subscribe("TSLA", contract)

# Get the ticker object
ticker = mdb._subs.get("TSLA")[1] if "TSLA" in mdb._subs else None
if ticker:
    print(f"\nTicker object: {ticker}")
    print(f"  ticker.last: {ticker.last}")
    print(f"  ticker.close: {ticker.close}")
    print(f"  ticker.marketPrice(): {ticker.marketPrice()}")
    print(f"  ticker.bid: {ticker.bid}")
    print(f"  ticker.ask: {ticker.ask}")
    print(f"  ticker.halted: {ticker.halted}")
    
    print("\nWaiting 5 seconds for live data...")
    time.sleep(5)
    
    print(f"  ticker.last: {ticker.last}")
    print(f"  ticker.close: {ticker.close}")
    print(f"  ticker.marketPrice(): {ticker.marketPrice()}")
    
    print("\nTrying get_last()...")
    price, ts = mdb.get_last("TSLA")
    print(f"  get_last() returned: {price} @ {ts}")
    
    print("\nWaiting 25 more seconds for fallback...")
    time.sleep(25)
    
    price, ts = mdb.get_last("TSLA")
    print(f"  After fallback: {price} @ {ts}")
else:
    print("ERROR: Could not get ticker!")

ibc.disconnect()