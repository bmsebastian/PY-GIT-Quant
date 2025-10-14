# dashboard.py - Add these endpoints to your Flask dashboard

from flask import Flask, jsonify, request
from config import (
    MAX_IB_SUBSCRIPTIONS,
    get_scanner_capacity,
    subscription_status,
    PRIORITY_POSITION,
    PRIORITY_SCANNER_TOP,
    PRIORITY_SCANNER_NORMAL
)

app = Flask(__name__)

# Assume you have these globals
# market_bus: MarketDataBus
# scanner: BreakoutScanner
# get_position_symbols(): function to get current positions


@app.route('/api/subscriptions', methods=['GET'])
def get_subscriptions():
    """Get subscription status summary."""
    try:
        position_symbols = get_position_symbols()
        current_subs = len(market_bus._subs)
        
        status = subscription_status(current_subs, len(position_symbols))
        
        return jsonify({
            "success": True,
            "data": status,
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/subscriptions/details', methods=['GET'])
def get_subscription_details():
    """Get detailed subscription information."""
    try:
        position_symbols = get_position_symbols()
        
        # Build detailed list
        symbols_info = []
        
        for symbol, (contract, ticker) in market_bus._subs.items():
            priority = market_bus._tracker.get_priority(symbol)
            last_price = None
            
            # Get last price
            if symbol in market_bus.tickers:
                last_price = market_bus.tickers[symbol].get('last')
            
            # Determine type
            if symbol in position_symbols:
                sub_type = "position"
            elif priority >= PRIORITY_SCANNER_TOP:
                sub_type = "scanner_top"
            else:
                sub_type = "scanner"
            
            symbols_info.append({
                "symbol": symbol,
                "priority": priority,
                "last_price": last_price,
                "type": sub_type,
                "subscription_time": market_bus._tracker.subscription_times.get(symbol, 0)
            })
        
        return jsonify({
            "success": True,
            "data": {
                "symbols": symbols_info,
                "total": len(symbols_info)
            },
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/subscriptions/capacity', methods=['GET'])
def get_subscription_capacity():
    """Get subscription capacity information."""
    try:
        position_symbols = get_position_symbols()
        position_count = len(position_symbols)
        capacity = get_scanner_capacity(position_count)
        current_subs = len(market_bus._subs)
        
        # Calculate utilization
        utilization = (current_subs / MAX_IB_SUBSCRIPTIONS) * 100
        
        # Get scanner info
        scanner_subs = current_subs - position_count
        scanner_utilization = (scanner_subs / capacity * 100) if capacity > 0 else 0
        
        return jsonify({
            "success": True,
            "data": {
                "total_subscriptions": current_subs,
                "limit": MAX_IB_SUBSCRIPTIONS,
                "utilization_pct": round(utilization, 1),
                "positions": {
                    "count": position_count,
                    "symbols": sorted(position_symbols)
                },
                "scanner": {
                    "capacity": capacity,
                    "active": scanner_subs,
                    "utilization_pct": round(scanner_utilization, 1),
                    "available": max(0, capacity - scanner_subs)
                },
                "status": "over_limit" if current_subs > MAX_IB_SUBSCRIPTIONS else
                         "near_limit" if current_subs >= 95 else "ok"
            },
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/subscriptions/cleanup', methods=['POST'])
def force_cleanup():
    """Force cleanup of excess subscriptions."""
    try:
        position_symbols = get_position_symbols()
        
        # Get current status
        before = len(market_bus._subs)
        
        # Run cleanup
        removed = market_bus.check_and_cleanup_subscriptions(position_symbols)
        
        # Get new status
        after = len(market_bus._subs)
        
        return jsonify({
            "success": True,
            "data": {
                "before": before,
                "after": after,
                "removed": removed,
                "position_symbols": sorted(position_symbols)
            },
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/subscriptions/unsubscribe/<symbol>', methods=['DELETE'])
def unsubscribe_symbol(symbol: str):
    """Manually unsubscribe from a symbol."""
    try:
        symbol = symbol.upper()
        
        # Check if it's a position (can't unsubscribe)
        position_symbols = get_position_symbols()
        if symbol in position_symbols:
            return jsonify({
                "success": False,
                "error": f"{symbol} is a position and cannot be unsubscribed"
            }), 400
        
        # Check if subscribed
        if symbol not in market_bus._subs:
            return jsonify({
                "success": False,
                "error": f"{symbol} is not subscribed"
            }), 404
        
        # Unsubscribe
        market_bus.unsubscribe(symbol)
        
        return jsonify({
            "success": True,
            "data": {
                "symbol": symbol,
                "action": "unsubscribed",
                "remaining_subscriptions": len(market_bus._subs)
            },
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check with subscription info."""
    try:
        position_symbols = get_position_symbols()
        status = subscription_status(len(market_bus._subs), len(position_symbols))
        
        # IB connection
        ib_connected = market_bus.ib.isConnected() if market_bus.ib else False
        
        # Get latest tick age
        tick_ages = []
        for symbol, data in market_bus.tickers.items():
            ts = data.get('ts')
            if ts:
                age = time.time() - ts
                tick_ages.append(age)
        
        avg_tick_age = sum(tick_ages) / len(tick_ages) if tick_ages else None
        
        return jsonify({
            "success": True,
            "data": {
                "status": "healthy" if not status['over_limit'] else "degraded",
                "ib_connected": ib_connected,
                "subscriptions": {
                    "current": status['current'],
                    "limit": status['limit'],
                    "status": status['status'],
                    "capacity": status['capacity']
                },
                "data_quality": {
                    "avg_tick_age_s": round(avg_tick_age, 1) if avg_tick_age else None,
                    "symbols_with_data": len([s for s, d in market_bus.tickers.items() if d.get('last')])
                },
                "uptime": getattr(STATE, 'uptime_seconds', 0)
            },
            "timestamp": time.time()
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# Example integration in main dashboard HTML
DASHBOARD_HTML_ADDITION = """
<!-- Add to your dashboard.html -->
<div class="subscription-status" id="subscription-status">
    <h3>Subscription Status</h3>
    <div class="status-bar">
        <div id="sub-usage-bar" class="usage-bar"></div>
    </div>
    <div class="status-details">
        <span id="sub-current">0</span> / <span id="sub-limit">100</span> subscriptions
        (<span id="sub-pct">0%</span>)
    </div>
    <div class="capacity-info">
        <small>
            Positions: <span id="sub-positions">0</span> | 
            Capacity: <span id="sub-capacity">0</span> slots
        </small>
    </div>
</div>

<script>
// Add to your dashboard JavaScript
function updateSubscriptionStatus() {
    fetch('/api/subscriptions/capacity')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const info = data.data;
                document.getElementById('sub-current').textContent = info.total_subscriptions;
                document.getElementById('sub-limit').textContent = info.limit;
                document.getElementById('sub-pct').textContent = info.utilization_pct + '%';
                document.getElementById('sub-positions').textContent = info.positions.count;
                document.getElementById('sub-capacity').textContent = info.scanner.available;
                
                // Update progress bar
                const bar = document.getElementById('sub-usage-bar');
                bar.style.width = info.utilization_pct + '%';
                
                // Color code by status
                if (info.status === 'over_limit') {
                    bar.className = 'usage-bar danger';
                } else if (info.status === 'near_limit') {
                    bar.className = 'usage-bar warning';
                } else {
                    bar.className = 'usage-bar success';
                }
            }
        })
        .catch(err => console.error('Failed to fetch subscription status:', err));
}

// Update every 5 seconds
setInterval(updateSubscriptionStatus, 5000);
updateSubscriptionStatus(); // Initial load
</script>

<style>
.subscription-status {
    padding: 15px;
    background: #f5f5f5;
    border-radius: 8px;
    margin: 10px 0;
}

.usage-bar {
    height: 20px;
    border-radius: 4px;
    transition: width 0.3s, background-color 0.3s;
}

.usage-bar.success { background-color: #28a745; }
.usage-bar.warning { background-color: #ffc107; }
.usage-bar.danger { background-color: #dc3545; }

.status-bar {
    background: #e0e0e0;
    border-radius: 4px;
    height: 20px;
    margin: 10px 0;
    overflow: hidden;
}
</style>
"""

# Print instructions for adding to dashboard
if __name__ == '__main__':
    print("Add these endpoints to your Flask dashboard:")
    print("- GET  /api/subscriptions")
    print("- GET  /api/subscriptions/details")
    print("- GET  /api/subscriptions/capacity")
    print("- POST /api/subscriptions/cleanup")
    print("- DELETE /api/subscriptions/unsubscribe/<symbol>")
    print("\nEnhanced /api/health endpoint included")
