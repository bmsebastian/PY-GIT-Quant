#!/usr/bin/env python3
# check_api.py - Query the dashboard API to see what data exists
"""
This queries the running dashboard to see what data is actually there.
Run this WHILE QTrade is running.
"""

import requests
import json

DASHBOARD_URL = "http://localhost:8052"

def check_status():
    """Check system status."""
    try:
        r = requests.get(f"{DASHBOARD_URL}/api/status", timeout=5)
        data = r.json()
        print("\n=== SYSTEM STATUS ===")
        print(f"IB Connected: {data['ib_connected']}")
        print(f"Market Phase: {data['market_phase']}")
        print(f"Subscriptions: {data['subscriptions']}/{data['max_subscriptions']}")
        print(f"Positions: {data['positions']}")
        print(f"Uptime: {data['uptime']}s")
        return True
    except Exception as e:
        print(f"\n❌ ERROR: Could not connect to dashboard at {DASHBOARD_URL}")
        print(f"   Make sure QTrade is running!")
        print(f"   Error: {e}")
        return False

def check_positions():
    """Check positions."""
    try:
        r = requests.get(f"{DASHBOARD_URL}/api/positions", timeout=5)
        data = r.json()
        print("\n=== POSITIONS ===")
        print(f"Total: {data['count']}")
        print(f"Total P&L: ${data['total_pnl']:.2f}")
        
        if data['positions']:
            print("\nDetails:")
            for pos in data['positions']:
                print(f"  {pos['symbol']:<6} {pos['sec_type']:<4} qty={pos['qty']:<4} "
                      f"last=${pos['last'] if pos['last'] else 0:.2f} "
                      f"pnl=${pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)")
        else:
            print("  (No positions)")
            
    except Exception as e:
        print(f"\n❌ ERROR checking positions: {e}")

def check_futures():
    """Check futures watchlist."""
    try:
        r = requests.get(f"{DASHBOARD_URL}/api/futures", timeout=5)
        data = r.json()
        print("\n=== FUTURES WATCHLIST ===")
        print(f"Total: {data['count']}")
        
        if data['futures']:
            print("\nDetails:")
            for fut in data['futures']:
                print(f"  {fut['symbol']:<6} ${fut['last'] if fut['last'] else 0:.2f} "
                      f"(mult: {fut['multiplier']}x, age: {fut['age']}s)")
        else:
            print("  (No futures)")
            
    except Exception as e:
        print(f"\n❌ ERROR checking futures: {e}")

def check_scanner():
    """Check scanner results."""
    try:
        r = requests.get(f"{DASHBOARD_URL}/api/scanner", timeout=5)
        data = r.json()
        print("\n=== SCANNER RESULTS ===")
        print(f"Total: {data['count']}")
        
        if data['results']:
            print("\nTop 5:")
            for result in data['results'][:5]:
                breakdown = result.get('breakdown', {})
                print(f"  {result['symbol']:<6} score={result['total_score']:.1f} "
                      f"grade={result['grade']} last=${result.get('last', 0):.2f}")
        else:
            print("  (No results - waiting for scan or market open)")
            
    except Exception as e:
        print(f"\n❌ ERROR checking scanner: {e}")

def main():
    print("=" * 60)
    print("QTrade Dashboard API Check")
    print("=" * 60)
    
    if not check_status():
        return
    
    check_positions()
    check_futures()
    check_scanner()
    
    print("\n" + "=" * 60)
    print("Check complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
