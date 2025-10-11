# dashboard_server.py
from flask import Flask, jsonify, render_template_string
from state_bus import STATE

_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>QTrade v13.5 Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,'Helvetica Neue',Arial,sans-serif;margin:24px;color:#111}
    h1{margin-top:0}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
    .card{border:1px solid #e5e7eb;border-radius:12px;padding:12px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
    .muted{color:#6b7280;font-size:12px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:left}
    th{font-size:12px;color:#6b7280}
    .pill{display:inline-block;padding:2px 8px;border-radius:999px;background:#f1f5f9;font-size:12px}
    .ok{background:#ecfdf5;color:#065f46}
    .warn{background:#fff7ed;color:#9a3412}
  </style>
</head>
<body>
  <h1>QTrade v13.5</h1>
  <div class="muted">ENV: {{env}} • DRY_RUN: {{dry_run}} • Symbols: {{symbols|length}} • Last heartbeat: {{heartbeat_ts}}</div>

  <div class="grid" style="margin-top:16px">
    <div class="card">
      <div><span class="pill {% if circuit_ok %}ok{% else %}warn{% endif %}">
        {% if circuit_ok %}OK{% else %}BREACHED{% endif %}
      </span> Circuit / Risk</div>
      <div class="muted" style="margin-top:8px">PnL Today: {{pnl_day}} • Open Orders: {{open_orders}}</div>
    </div>
    <div class="card">
      <div>Subscriptions</div>
      <div class="muted" style="margin-top:8px">Total: {{subs}}</div>
      <div class="muted">Live Mode: {{live_mode}}</div>
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>Prices</div>
      <div class="muted"><a href="/api/snapshot">/api/snapshot</a></div>
    </div>
    <table style="margin-top:8px">
      <thead><tr><th>Symbol</th><th>Last</th><th>Bid</th><th>Ask</th></tr></thead>
      <tbody>
        {% for row in prices %}
          <tr>
            <td>{{row.symbol}}</td>
            <td>{{row.last}}</td>
            <td>{{row.bid}}</td>
            <td>{{row.ask}}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</body>
</html>
"""

def create_app():
    app = Flask(__name__)

    @app.get("/api/snapshot")
    def api_snapshot():
        return jsonify(STATE.get())

    @app.get("/")
    def home():
        state = STATE.get()
        prices = state.get("prices", [])
        return render_template_string(
            _HTML,
            env=state.get("env"),
            dry_run=state.get("dry_run"),
            subs=state.get("subs"),
            open_orders=state.get("open_orders"),
            pnl_day=state.get("pnl_day"),
            heartbeat_ts=int(state.get("heartbeat_ts", 0)),
            symbols=state.get("symbols", []),
            prices=prices,
            circuit_ok=state.get("circuit_ok", True),
            live_mode=state.get("live_mode", False),
        )

    return app

def start_dashboard(host: str = "127.0.0.1", port: int = 8052):
    from threading import Thread
    app = create_app()
    th = Thread(target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False), daemon=True)
    th.start()
    return th
