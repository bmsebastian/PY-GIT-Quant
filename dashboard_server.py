
from flask import Flask, jsonify, render_template_string
from state_bus import STATE

_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>QTrade v14 — Live</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,'Helvetica Neue',Arial,sans-serif;margin:24px;color:#111}
    h1{margin-top:0}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
    .card{border:1px solid #e5e7eb;border-radius:12px;padding:12px;box-shadow:0 1px 2px rgba(0,0,0,.04);margin-top:16px}
    .muted{color:#6b7280;font-size:12px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:left;vertical-align:middle}
    th{font-size:12px;color:#6b7280}
    .pill{display:inline-block;padding:2px 8px;border-radius:999px;background:#f1f5f9;font-size:12px}
    .ok{background:#ecfdf5;color:#065f46}
    .warn{background:#fff7ed;color:#9a3412}
    canvas.spark{width:120px;height:28px}
    #toasts{position:fixed;top:12px;right:12px;display:flex;flex-direction:column;gap:8px;z-index:9999}
    .toast{background:#111;color:#fff;border-radius:10px;padding:10px 12px;box-shadow:0 6px 16px rgba(0,0,0,.2);opacity:.95}
    .toast.up{background:#065f46}
    .toast.down{background:#9a3412}
  </style>
</head>
<body>
  <h1>QTrade v14</h1>

  <div class="muted" id="hdr">
    ENV: <span id="env"></span> • DRY_RUN: <span id="dry"></span>
    • Subs: <span id="subs">0</span> • Prices: <span id="prices">0</span>
    • IB: <span id="ib">false</span>
    • Last tick: <span id="tickage">-</span>s
    • Pos sync: <span id="posage">-</span>s
    • Uptime: <span id="uptime">00:00:00</span>
    • Loop lag: <span id="lag">-</span>ms
    • HB: <span id="hbts">-</span>
  </div>

  <div class="grid">
    <div class="card">
      <div><span id="circuit" class="pill ok">OK</span> Circuit / Risk</div>
      <div class="muted" style="margin-top:8px">PnL Today: <span id="pnl">0</span> • Open Orders: <span id="orders">0</span></div>
    </div>
    <div class="card">
      <div>Subscriptions</div>
      <div class="muted" style="margin-top:8px">Total: <span id="subs2">0</span></div>
      <div class="muted">Live Mode: <span id="live">false</span></div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>Positions (Live)</div>
    </div>
    <table style="margin-top:8px" id="posTbl">
      <thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Last</th><th>EMA8</th><th>EMA21</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

<script>
function fmt(x, d=2){
  if (x===null || x===undefined || Number.isNaN(x)) return "nan";
  return Number(x).toFixed(d);
}
function hhmmss(s){
  s = Math.max(0, parseInt(s||0,10));
  const h = String(Math.floor(s/3600)).padStart(2,'0');
  const m = String(Math.floor((s%3600)/60)).padStart(2,'0');
  const sec = String(s%60).padStart(2,'0');
  return `${h}:${m}:${sec}`;
}
async function refreshSnapshot(){
  const res = await fetch('/api/snapshot');
  const st = await res.json();
  document.getElementById('env').textContent = st.env || '';
  document.getElementById('dry').textContent = String(st.dry_run) || 'false';
  document.getElementById('subs').textContent = st.subs || 0;
  document.getElementById('subs2').textContent = st.subs || 0;
  document.getElementById('live').textContent = st.live_mode ? 'true' : 'false';

  document.getElementById('pnl').textContent = fmt(st.pnl_day||0,2);
  document.getElementById('orders').textContent = st.open_orders||0;

  // positions
  const posBody = document.querySelector('#posTbl tbody');
  posBody.innerHTML = '';
  (st.positions||[]).forEach(row=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.symbol}</td>
      <td>${row.qty}</td>
      <td>${fmt(row.avg)}</td>
      <td>${fmt(row.last)}</td>
      <td>${fmt(row.ema8)}</td>
      <td>${fmt(row.ema21)}</td>
    `;
    posBody.appendChild(tr);
  });
}
async function refreshHeartbeat(){
  const r = await fetch('/api/heartbeat');
  const hb = await r.json();
  document.getElementById('prices').textContent = hb.symbols ?? hb.prices ?? 0;
  document.getElementById('ib').textContent = hb.ib_connected ? 'true' : 'false';
  document.getElementById('tickage').textContent = (hb.last_tick_age_s ?? '-');
  document.getElementById('posage').textContent = (hb.last_pos_sync_age_s ?? '-');
  document.getElementById('uptime').textContent = hhmmss(hb.uptime_s ?? 0);
  document.getElementById('lag').textContent = hb.loop_lag_ms ?? '-';
  document.getElementById('hbts').textContent = hb.ts || hb.seq || '-';
}
setInterval(refreshSnapshot, 2000);
setInterval(refreshHeartbeat, 60000);
refreshSnapshot();
refreshHeartbeat();
</script>
</body>
</html>
"""

def create_app():
    app = Flask(__name__)

    @app.get("/api/snapshot")
    def api_snapshot():
        return jsonify(STATE.get())

    @app.get("/api/heartbeat")
    def api_heartbeat():
        s = STATE.get()
        hb = s.get("heartbeat", {})
        return jsonify(hb or {})

    @app.get("/")
    def home():
        return render_template_string(_HTML)

    return app

def start_dashboard(host: str = "127.0.0.1", port: int = 8052):
    from threading import Thread
    app = create_app()
    th = Thread(target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False), daemon=True)
    th.start()
    return th
