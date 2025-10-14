#!/usr/bin/env python3
# debug_state.py - Check what's actually in STATE
"""
Run this while QTrade is running to see what data we have.
"""

import time
from state_bus import STATE

print("=" * 60)
print("STATE DEBUG - Current Data")
print("=" * 60)

# Wait a moment for data to populate
time.sleep(2)

print("\n--- POSITIONS ---")
print(f"Total positions: {len(STATE.positions)}")
for symbol, pos in STATE.positions.items():
    print(f"  {symbol}: {pos.get('sec_type', 'STK')} qty={pos.get('qty', 0)}")

print("\n--- PRICES ---")
print(f"Total prices: {len(STATE.prices)}")
for symbol, price_data in list(STATE.prices.items())[:15]:  # Show first 15
    last = price_data.get('last')
    age = price_data.get('age', 999)
    print(f"  {symbol}: ${last if last else 0:.2f} (age: {age}s)")

print("\n--- SUBSCRIPTIONS ---")
print(f"Total subscribed: {len(STATE.symbols_subscribed)}")
for symbol in sorted(STATE.symbols_subscribed):
    print(f"  {symbol}")

print("\n--- SCANNER RESULTS ---")
scanner_results = getattr(STATE, 'scanner_results', [])
print(f"Total scanner results: {len(scanner_results)}")
for result in scanner_results[:5]:  # Show first 5
    print(f"  {result['symbol']}: {result['total_score']:.1f} ({result['grade']})")

print("\n--- MARKET PHASE ---")
print(f"Phase: {getattr(STATE, 'market_phase', 'unknown')}")

print("\n=" * 60)
print("Press Ctrl+C to exit")
print("=" * 60)

# Keep running
try:
    while True:
        time.sleep(5)
        
        # Update display every 5 seconds
        print(f"\n[{time.strftime('%H:%M:%S')}] Positions: {len(STATE.positions)} | Prices: {len(STATE.prices)} | Subs: {len(STATE.symbols_subscribed)}")
        
        # Show if any futures have prices
        for sym in ['NQ', 'ES', 'CL', 'GC', 'NQZ5', 'ESZ5', 'CLZ5', 'GCZ5']:
            if sym in STATE.prices:
                price = STATE.prices[sym].get('last')
                age = STATE.prices[sym].get('age', 999)
                print(f"  {sym}: ${price if price else 0:.2f} (age: {age}s)")

except KeyboardInterrupt:
    print("\nDebug stopped")
