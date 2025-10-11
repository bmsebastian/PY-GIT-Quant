from flask import Flask, jsonify, render_template_string
from state_bus import STATE

_HTML = """
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
    .toast.up{background:#065f46}  /* green */
    .toast.down{background:#9a3412}/* orange */
  </style>
</head>
<body>
  <h1>QTrade v14</h1>
  <div class="muted">ENV: <span id="env"></span> • DRY_RUN: <span id="dry"></span> • Symbols: <span id="symc"></span> • Last heartbeat: <span id="hb"></span></div>

  <div class="grid">
    <div class="card">
      <div><span id="circuit" class="pill ok">OK</span> Circuit / Risk</div>
      <div class="muted" style="margin-top:8px">PnL Today: <span id="pnl">0</span> • Open Orders: <span id="orders">0</span></div>
    </div>
    <div class="card">
      <div>Subscriptions</div>
      <div class="muted" style="margin-top:8px">Total: <span id="subs">0</span></div>
      <div class="muted">Live Mode: <span id="live">false</span></div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>Positions (Live)</div>
    </div>
    <table style="margin-top:8px" id="posTbl">
      <thead><tr><th>Symbol</th><th>Last</th><th>EMA8</th><th>EMA21</th><th>ATR</th><th>Signal</th><th>Trend</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>Breakout Watchlist (Strict)</div>
    </div>
    <table style="margin-top:8px" id="boTbl">
      <thead><tr><th>Symbol</th><th>Label</th><th>Dir</th><th>Score</th><th>Last</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div id="toasts"></div>

<script>
let lastAlertId = 0;

function fmt(x, d=2){
  if (x===null || x===undefined || Number.isNaN(x)) return "nan";
  return Number(x).toFixed(d);
}

function drawSpark(canvas, series){
  if (!canvas || !series || series.length < 2) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width = canvas.clientWidth;
  const h = canvas.height = canvas.clientHeight;
  ctx.clearRect(0,0,w,h);
  const min = Math.min(...series);
  const max = Math.max(...series);
  const rng = (max-min) || 1;
  const pad = 2;
  const step = (w-2*pad)/(series.length-1);
  ctx.beginPath();
  ctx.moveTo(pad, h - ((series[0]-min)/rng)*(h-2*pad) - pad);
  for (let i=1;i<series.length;i++){
    const x = pad + i*step;
    const y = h - ((series[i]-min)/rng)*(h-2*pad) - pad;
    ctx.lineTo(x,y);
  }
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = '#0ea5e9';
  ctx.stroke();
}

function toast(msg, kind){
  const box = document.getElementById('toasts');
  const div = document.createElement('div');
  div.className = 'toast ' + (kind||'');
  div.textContent = msg;
  box.appendChild(div);
  // Sound via WebAudio
  try{
    const ac = new (window.AudioContext||window.webkitAudioContext)();
    const o = ac.createOscillator();
    const g = ac.createGain();
    o.type = 'sine';
    o.frequency.setValueAtTime(kind==='up'? 880: 440, ac.currentTime);
    g.gain.setValueAtTime(0.0001, ac.currentTime);
    g.gain.exponentialRampToValueAtTime(0.15, ac.currentTime+0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime+0.25);
    o.connect(g); g.connect(ac.destination); o.start(); o.stop(ac.currentTime+0.26);
  }catch(e){}
  setTimeout(()=>{ div.remove(); }, 3500);
}

async function refresh(){
  const res = await fetch('/api/snapshot');
  const st = await res.json();

  // header
  document.getElementById('env').textContent = st.env;
  document.getElementById('dry').textContent = st.dry_run;
  document.getElementById('symc').textContent = (st.symbols||[]).length;
  document.getElementById('hb').textContent = Math.trunc(st.heartbeat_ts||0);
  document.getElementById('subs').textContent = st.subs||0;
  document.getElementById('live').textContent = st.live_mode? 'true':'false';
  document.getElementById('pnl').textContent = fmt(st.pnl_day||0,2);
  document.getElementById('orders').textContent = st.open_orders||0;
  const c = document.getElementById('circuit');
  if (st.circuit_ok) { c.classList.add('ok'); c.classList.remove('warn'); c.textContent='OK'; }
  else { c.classList.add('warn'); c.classList.remove('ok'); c.textContent='BREACHED'; }

  // positions
  const posBody = document.querySelector('#posTbl tbody');
  posBody.innerHTML = '';
  (st.positions||[]).forEach(row=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.symbol}</td>
      <td>${fmt(row.last)}</td>
      <td>${fmt(row.ema_fast)}</td>
      <td>${fmt(row.ema_slow)}</td>
      <td>${fmt(row.atr)}</td>
      <td>${row.signal||''}</td>
      <td><canvas class="spark"></canvas></td>
    `;
    posBody.appendChild(tr);
    const canvas = tr.querySelector('canvas.spark');
    drawSpark(canvas, row.series||[]);
  });

  // breakouts
  const boBody = document.querySelector('#boTbl tbody');
  boBody.innerHTML = '';
  (st.breakouts||[]).forEach(row=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.symbol}</td>
      <td>${row.label||''}</td>
      <td>${row.signal||''}</td>
      <td>${fmt(row.score)}</td>
      <td>${fmt(row.last)}</td>
    `;
    boBody.appendChild(tr);
  });

  // alerts
  (st.alerts||[]).forEach(a=>{
    if (a.id > lastAlertId){
      lastAlertId = a.id;
      toast(a.text, a.kind);
    }
  });
}

setInterval(refresh, 2000);
refresh();
</script>
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
        # initial render; live updates via JS polling
        state = STATE.get()
        return render_template_string(_HTML)

    return app

def start_dashboard(host: str = "127.0.0.1", port: int = 8052):
    from threading import Thread
    app = create_app()
    th = Thread(target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False), daemon=True)
    th.start()
    return th
