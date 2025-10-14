#!/usr/bin/env python3
# test_filtering.py - Test which symbols get filtered

from contracts import looks_nontradable_symbol

# Your actual positions
positions = [
    "TOGI",
    "MRAI", 
    "KALRQ",
    "AZREF",
    "CNCE.CVR",
    "TOGIW",
    "RFP.CVR",
    "NQZ5",
    "TSLA",
    "FUSN.CVR",
    "CLZ5",
    "ALPSQ.OLD"
]

print("=" * 60)
print("QTrade Position Filtering Test")
print("=" * 60)
print()

kept = []
filtered = []

for symbol in positions:
    if looks_nontradable_symbol(symbol):
        filtered.append(symbol)
        print(f"❌ FILTER: {symbol:<15} - Non-tradable")
    else:
        kept.append(symbol)
        print(f"✅ KEEP:   {symbol:<15} - Tradable")

print()
print("=" * 60)
print(f"Summary:")
print(f"  Total positions: {len(positions)}")
print(f"  Kept: {len(kept)} - {', '.join(kept)}")
print(f"  Filtered: {len(filtered)} - {', '.join(filtered)}")
print("=" * 60)
print()
print("Dashboard will show ONLY the kept positions.")
print("This prevents NaN errors and clutter.")
