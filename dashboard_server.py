# dashboard_server.py - v15C Multi-Asset Dashboard (FIXED)
"""
Professional 4-section dashboard:
1. Positions - Open trades with live P&L
2. Futures/Indexes - Watchlist real-time prices  
3. Unusual Options - Top 10 UOA
4. Scanner Stocks - Top breakout opportunities

v15C FIXES:
- Properly handle futures symbol mapping (NQ vs NQZ5)
- Show live data for all subscribed symbols
- Fix age calculation for stale detection
"""

import logging
from flask import Flask, jsonify, render_template_string
from datetime import datetime

from config import *
from state_bus import STATE

logger = logging.getLogger(__name__)

app = Flask(__name__)


def format_currency(value):
    """Format number as currency."""
    if value is None:
        return "$0.00"
    return f"${value:,.2f}"


def format_percent(value):
    """Format number as percentage."""
    if value is None:
        return "0.00%"
    return f"{value:+.2f}%"


@app.route('/')
def index():
    """Serve main dashboard page."""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/status')
def api_status():
    """System status endpoint."""
    market_phase = getattr(STATE, 'market_phase', 'unknown')
    
    return jsonify({
        'uptime': STATE.uptime_seconds(),
        'ib_connected': STATE.ib_connected,
        'market_phase': market_phase,
        'subscriptions': len(STATE.symbols_subscribed),
        'max_subscriptions': IB_MAX_SUBSCRIPTIONS,
        'positions': len(STATE.positions),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/positions')
def api_positions():
    """Positions with live P&L - includes ALL positions (stocks + futures)."""
    positions_list = []
    
    for symbol, pos in STATE.positions.items():
        try:
            # For futures (CLZ5, NQZ5), the symbol IS the key
            # For stocks (TSLA, TOGI), same
            price_data = STATE.prices.get(symbol, {})
            
            last = price_data.get('last')
            age = price_data.get('age', 999)
            
            # Get position details
            qty = pos.get('qty', 0)
            avg_cost = pos.get('avg', 0)
            sec_type = pos.get('sec_type', 'STK')
            multiplier = pos.get('multiplier', 1)
            
            # Calculate P&L
            if last and avg_cost:
                pnl = (last - avg_cost) * qty * multiplier
                pnl_pct = ((last / avg_cost) - 1) * 100 if avg_cost > 0 else 0
            else:
                pnl = 0
                pnl_pct = 0
            
            positions_list.append({
                'symbol': symbol,
                'qty': qty,
                'avg': avg_cost,
                'last': last,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'sec_type': sec_type,
                'multiplier': multiplier,
                'age': age
            })
            
        except Exception as e:
            logger.error(f"Position API error for {symbol}: {e}")
            continue
    
    # Calculate total P&L
    total_pnl = sum(p['pnl'] for p in positions_list)
    
    return jsonify({
        'positions': positions_list,
        'total_pnl': total_pnl,
        'count': len(positions_list)
    })


@app.route('/api/futures')
def api_futures():
    """
    Futures watchlist prices.
    
    v15C FIX: Handle futures symbol mapping
    Futures may be subscribed as NQZ5, ESZ5, etc. but we want to display as NQ, ES.
    """
    futures_list = []
    
    for root_symbol in FUTURES_WATCHLIST:
        try:
            # Try root symbol first (NQ, ES, etc.)
            price_data = STATE.prices.get(root_symbol, {})
            
            # If not found, try to find any subscribed symbol starting with root
            if not price_data or price_data.get('last') is None:
                for subscribed_symbol in STATE.symbols_subscribed:
                    if subscribed_symbol.startswith(root_symbol):
                        price_data = STATE.prices.get(subscribed_symbol, {})
                        if price_data.get('last') is not None:
                            break
            
            last = price_data.get('last')
            age = price_data.get('age', 999)
            
            futures_list.append({
                'symbol': root_symbol,
                'last': last,
                'age': age,
                'multiplier': FUTURES_MULTIPLIERS.get(root_symbol, 1)
            })
            
        except Exception as e:
            logger.error(f"Futures API error for {root_symbol}: {e}")
            continue
    
    return jsonify({
        'futures': futures_list,
        'count': len(futures_list)
    })


@app.route('/api/options')
def api_options():
    """Unusual options activity."""
    options = getattr(STATE, 'unusual_options', [])
    
    return jsonify({
        'options': options,
        'count': len(options)
    })


@app.route('/api/scanner')
def api_scanner():
    """Scanner results with scores."""
    scanner_results = getattr(STATE, 'scanner_results', [])
    
    return jsonify({
        'results': scanner_results,
        'count': len(scanner_results)
    })


# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QTrade v15 Professional Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 1800px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            font-size: 28px;
            color: #1a1a1a;
            margin-bottom: 10px;
        }
        
        .status-bar {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-label {
            color: #666;
            font-size: 14px;
        }
        
        .status-value {
            font-weight: 600;
            font-size: 14px;
        }
        
        .indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .indicator.green {
            background: #22c55e;
        }
        
        .indicator.red {
            background: #ef4444;
        }
        
        .indicator.yellow {
            background: #eab308;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(800px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
        }
        
        .card-title {
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
        }
        
        .card-count {
            font-size: 14px;
            color: #666;
            background: #f3f4f6;
            padding: 4px 12px;
            border-radius: 12px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            text-align: left;
            padding: 10px;
            font-size: 12px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #e5e7eb;
        }
        
        td {
            padding: 12px 10px;
            font-size: 14px;
            border-bottom: 1px solid #f3f4f6;
        }
        
        tr:hover {
            background: #f9fafb;
        }
        
        .symbol {
            font-weight: 600;
            color: #1a1a1a;
        }
        
        .positive {
            color: #22c55e;
            font-weight: 600;
        }
        
        .negative {
            color: #ef4444;
            font-weight: 600;
        }
        
        .neutral {
            color: #666;
        }
        
        .score-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .score-a {
            background: #dcfce7;
            color: #166534;
        }
        
        .score-b {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .score-c {
            background: #fef3c7;
            color: #92400e;
        }
        
        .pnl-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 30px;
        }
        
        .pnl-label {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        
        .pnl-value {
            font-size: 36px;
            font-weight: 700;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        
        @media (max-width: 1200px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>QTrade v15 Professional Dashboard</h1>
            <div class="status-bar">
                <div class="status-item">
                    <span class="indicator green" id="ib-indicator"></span>
                    <span class="status-label">IB:</span>
                    <span class="status-value" id="ib-status">Connected</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Market:</span>
                    <span class="status-value" id="market-phase">Regular</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Subscriptions:</span>
                    <span class="status-value" id="subscription-count">0/50</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Uptime:</span>
                    <span class="status-value" id="uptime">0m</span>
                </div>
            </div>
        </header>
        
        <div class="grid">
            <!-- Total P&L Card -->
            <div class="card pnl-card">
                <div class="pnl-label">Total P&L Today</div>
                <div class="pnl-value" id="total-pnl">$0.00</div>
            </div>
        </div>
        
        <div class="grid">
            <!-- Positions -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Open Positions</span>
                    <span class="card-count" id="positions-count">0</span>
                </div>
                <table id="positions-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Qty</th>
                            <th>Avg Cost</th>
                            <th>Last</th>
                            <th>P&L</th>
                            <th>P&L %</th>
                            <th>Type</th>
                        </tr>
                    </thead>
                    <tbody id="positions-body">
                        <tr><td colspan="7" class="loading">Loading positions...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <!-- Futures Watchlist -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Futures Watchlist</span>
                    <span class="card-count" id="futures-count">7</span>
                </div>
                <table id="futures-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Last Price</th>
                            <th>Multiplier</th>
                            <th>Data Age</th>
                        </tr>
                    </thead>
                    <tbody id="futures-body">
                        <tr><td colspan="4" class="loading">Loading futures...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="grid">
            <!-- Scanner Results -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Breakout Scanner</span>
                    <span class="card-count" id="scanner-count">0</span>
                </div>
                <table id="scanner-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Score</th>
                            <th>Grade</th>
                            <th>Last</th>
                            <th>RS</th>
                            <th>Volume</th>
                            <th>Momentum</th>
                        </tr>
                    </thead>
                    <tbody id="scanner-body">
                        <tr><td colspan="7" class="loading">Waiting for scan...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <!-- Unusual Options -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Unusual Options Activity</span>
                    <span class="card-count" id="options-count">0</span>
                </div>
                <table id="options-table">
                    <thead>
                        <tr>
                            <th>Contract</th>
                            <th>Score</th>
                            <th>Volume</th>
                            <th>OI</th>
                            <th>Premium</th>
                            <th>IV</th>
                            <th>Sweep</th>
                        </tr>
                    </thead>
                    <tbody id="options-body">
                        <tr><td colspan="7" class="loading">Waiting for scan...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        function formatCurrency(value) {
            if (value == null || isNaN(value)) return '$0.00';
            return '$' + value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }
        
        function formatPercent(value) {
            if (value == null || isNaN(value)) return '0.00%';
            const sign = value >= 0 ? '+' : '';
            return sign + value.toFixed(2) + '%';
        }
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) return `${hours}h ${minutes}m`;
            return `${minutes}m`;
        }
        
        function updateStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    // IB Connection
                    const ibIndicator = document.getElementById('ib-indicator');
                    const ibStatus = document.getElementById('ib-status');
                    if (data.ib_connected) {
                        ibIndicator.className = 'indicator green';
                        ibStatus.textContent = 'Connected';
                    } else {
                        ibIndicator.className = 'indicator red';
                        ibStatus.textContent = 'Disconnected';
                    }
                    
                    // Market Phase
                    const marketPhase = document.getElementById('market-phase');
                    marketPhase.textContent = data.market_phase.toUpperCase();
                    
                    // Subscriptions
                    const subCount = document.getElementById('subscription-count');
                    subCount.textContent = `${data.subscriptions}/${data.max_subscriptions}`;
                    
                    // Uptime
                    const uptime = document.getElementById('uptime');
                    uptime.textContent = formatUptime(data.uptime);
                })
                .catch(err => console.error('Status fetch error:', err));
        }
        
        function updatePositions() {
            fetch('/api/positions')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('positions-body');
                    const countEl = document.getElementById('positions-count');
                    const totalPnlEl = document.getElementById('total-pnl');
                    
                    countEl.textContent = data.count;
                    
                    if (data.positions.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No open positions</td></tr>';
                        totalPnlEl.textContent = '$0.00';
                        totalPnlEl.style.color = 'white';
                        return;
                    }
                    
                    const rows = data.positions.map(pos => {
                        const pnlClass = pos.pnl >= 0 ? 'positive' : 'negative';
                        return `
                            <tr>
                                <td class="symbol">${pos.symbol}</td>
                                <td>${pos.qty}</td>
                                <td>${formatCurrency(pos.avg)}</td>
                                <td>${formatCurrency(pos.last)}</td>
                                <td class="${pnlClass}">${formatCurrency(pos.pnl)}</td>
                                <td class="${pnlClass}">${formatPercent(pos.pnl_pct)}</td>
                                <td>${pos.sec_type}</td>
                            </tr>
                        `;
                    });
                    
                    tbody.innerHTML = rows.join('');
                    
                    // Update total P&L
                    totalPnlEl.textContent = formatCurrency(data.total_pnl);
                    totalPnlEl.style.color = data.total_pnl >= 0 ? '#22c55e' : '#ef4444';
                })
                .catch(err => console.error('Positions fetch error:', err));
        }
        
        function updateFutures() {
            fetch('/api/futures')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('futures-body');
                    
                    if (data.futures.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No futures data</td></tr>';
                        return;
                    }
                    
                    const rows = data.futures.map(fut => {
                        const ageClass = fut.age < 30 ? 'positive' : (fut.age < 60 ? 'neutral' : 'negative');
                        return `
                            <tr>
                                <td class="symbol">${fut.symbol}</td>
                                <td>${formatCurrency(fut.last)}</td>
                                <td>${fut.multiplier}x</td>
                                <td class="${ageClass}">${fut.age}s</td>
                            </tr>
                        `;
                    });
                    
                    tbody.innerHTML = rows.join('');
                })
                .catch(err => console.error('Futures fetch error:', err));
        }
        
        function updateScanner() {
            fetch('/api/scanner')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('scanner-body');
                    const countEl = document.getElementById('scanner-count');
                    
                    countEl.textContent = data.count;
                    
                    if (data.results.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Waiting for scan results...</td></tr>';
                        return;
                    }
                    
                    const rows = data.results.map(res => {
                        const gradeClass = `score-${res.grade.toLowerCase()}`;
                        const breakdown = res.breakdown || {};
                        return `
                            <tr>
                                <td class="symbol">${res.symbol}</td>
                                <td><strong>${res.total_score}</strong></td>
                                <td><span class="score-badge ${gradeClass}">${res.grade}</span></td>
                                <td>${formatCurrency(res.last || 0)}</td>
                                <td>${(breakdown.relative_strength || 0).toFixed(1)}</td>
                                <td>${(breakdown.volume || 0).toFixed(1)}</td>
                                <td>${(breakdown.momentum || 0).toFixed(1)}</td>
                            </tr>
                        `;
                    });
                    
                    tbody.innerHTML = rows.join('');
                })
                .catch(err => console.error('Scanner fetch error:', err));
        }
        
        function updateOptions() {
            fetch('/api/options')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('options-body');
                    const countEl = document.getElementById('options-count');
                    
                    countEl.textContent = data.count;
                    
                    if (data.options.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Waiting for options scan...</td></tr>';
                        return;
                    }
                    
                    const rows = data.options.map(opt => {
                        const sweepFlag = opt.is_sweep ? '🔥' : '';
                        return `
                            <tr>
                                <td class="symbol">${opt.contract_label}</td>
                                <td><strong>${opt.score}</strong></td>
                                <td>${opt.volume.toLocaleString()}</td>
                                <td>${opt.oi.toLocaleString()}</td>
                                <td>${formatCurrency(opt.premium)}</td>
                                <td>${(opt.iv * 100).toFixed(1)}%</td>
                                <td>${sweepFlag}</td>
                            </tr>
                        `;
                    });
                    
                    tbody.innerHTML = rows.join('');
                })
                .catch(err => console.error('Options fetch error:', err));
        }
        
        function updateAll() {
            updateStatus();
            updatePositions();
            updateFutures();
            updateScanner();
            updateOptions();
        }
        
        // Initial load
        updateAll();
        
        // Refresh every 2 seconds
        setInterval(updateAll, 2000);
    </script>
</body>
</html>
"""


def run_dashboard():
    """Start the dashboard server."""
    logger.info(f"Starting dashboard on {DASHBOARD_HOST}:{DASHBOARD_PORT}")
    app.run(
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        debug=DASHBOARD_DEBUG,
        threaded=True
    )


if __name__ == '__main__':
    run_dashboard()
