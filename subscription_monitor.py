#!/usr/bin/env python3
# scripts/monitor_subscriptions.py - Monitor IB subscription usage

import sys
import json
import requests
import argparse
from typing import Dict, Optional

# Assumes your system exposes /api/subscriptions endpoint
API_BASE = "http://localhost:5000"


def get_subscription_status() -> Optional[Dict]:
    """Fetch subscription status from API."""
    try:
        response = requests.get(f"{API_BASE}/api/subscriptions", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching status: {e}", file=sys.stderr)
        return None


def format_status(status: Dict) -> str:
    """Format subscription status for display."""
    current = status.get('current', 0)
    limit = status.get('limit', 100)
    positions = status.get('positions', 0)
    capacity = status.get('capacity', 0)
    over_limit = status.get('over_limit', False)
    near_limit = status.get('near_limit', False)
    
    # Usage bar
    pct = (current / limit) * 100 if limit > 0 else 0
    bar_len = 40
    filled = int((pct / 100) * bar_len)
    bar = '█' * filled + '░' * (bar_len - filled)
    
    # Color coding
    if over_limit:
        status_icon = "🔴"
        status_text = "OVER LIMIT"
    elif near_limit:
        status_icon = "🟡"
        status_text = "NEAR LIMIT"
    else:
        status_icon = "🟢"
        status_text = "OK"
    
    output = f"""
╔═══════════════════════════════════════════════════════════════╗
║           IB MARKET DATA SUBSCRIPTION STATUS                  ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Status: {status_icon} {status_text:<48} ║
║                                                               ║
║  Usage:  {current:3d} / {limit:3d} subscriptions ({pct:5.1f}%)                ║
║  [{bar}]  ║
║                                                               ║
║  Breakdown:                                                   ║
║    • Positions:       {positions:3d} symbols                           ║
║    • Scanner capacity: {capacity:3d} slots available                   ║
║                                                               ║
"""
    
    if over_limit:
        excess = status.get('excess', 0)
        output += f"║  ⚠️  WARNING: {excess} subscriptions over limit!                  ║\n"
        output += f"║      System should auto-remove lowest priority symbols    ║\n"
    elif near_limit:
        output += f"║  ⚠️  WARNING: Approaching subscription limit              ║\n"
        output += f"║      Only {capacity} slots remain for scanner symbols             ║\n"
    
    output += "╚═══════════════════════════════════════════════════════════════╝\n"
    
    return output


def get_top_subscriptions(limit: int = 10) -> Optional[Dict]:
    """Fetch top subscribed symbols."""
    try:
        response = requests.get(f"{API_BASE}/api/subscriptions/details", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching details: {e}", file=sys.stderr)
        return None


def format_subscription_details(details: Dict, limit: int = 10):
    """Format detailed subscription list."""
    symbols = details.get('symbols', [])
    
    # Sort by priority
    symbols.sort(key=lambda x: x.get('priority', 0), reverse=True)
    
    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│                    ACTIVE SUBSCRIPTIONS                     │")
    print("├──────────┬──────────┬──────────────┬──────────────────────┤")
    print("│ Symbol   │ Priority │ Last Price   │ Type                 │")
    print("├──────────┬──────────┬──────────────┬──────────────────────┤")
    
    for i, sym in enumerate(symbols[:limit]):
        symbol = sym.get('symbol', 'N/A')
        priority = sym.get('priority', 0)
        last_price = sym.get('last_price', 'N/A')
        sub_type = sym.get('type', 'scanner')
        
        # Format price
        if isinstance(last_price, (int, float)):
            price_str = f"${last_price:,.2f}"
        else:
            price_str = str(last_price)
        
        # Priority label
        if priority >= 100:
            pri_label = "POSITION"
        elif priority >= 50:
            pri_label = "HIGH"
        else:
            pri_label = "NORMAL"
        
        print(f"│ {symbol:<8} │ {pri_label:<8} │ {price_str:>12} │ {sub_type:<20} │")
    
    if len(symbols) > limit:
        remaining = len(symbols) - limit
        print(f"│ ... and {remaining} more symbols                                   │")
    
    print("└──────────┴──────────┴──────────────┴──────────────────────┘")


def main():
    parser = argparse.ArgumentParser(description="Monitor IB subscription usage")
    parser.add_argument('--details', '-d', action='store_true', 
                       help='Show detailed subscription list')
    parser.add_argument('--limit', '-l', type=int, default=10,
                       help='Limit for detailed view (default: 10)')
    parser.add_argument('--json', '-j', action='store_true',
                       help='Output raw JSON')
    parser.add_argument('--watch', '-w', action='store_true',
                       help='Watch mode (refresh every 5s)')
    
    args = parser.parse_args()
    
    try:
        while True:
            # Get status
            status = get_subscription_status()
            
            if status is None:
                print("❌ Failed to fetch subscription status", file=sys.stderr)
                return 1
            
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                # Clear screen in watch mode
                if args.watch:
                    print("\033[2J\033[H", end='')
                
                # Show status
                print(format_status(status))
                
                # Show details if requested
                if args.details:
                    details = get_top_subscriptions(args.limit)
                    if details:
                        format_subscription_details(details, args.limit)
            
            # Exit if not in watch mode
            if not args.watch:
                break
            
            # Wait before refresh
            import time
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        return 0
    
    return 0


if __name__ == '__main__':
    exit(main())
