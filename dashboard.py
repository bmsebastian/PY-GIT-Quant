# dashboard.py — Quant v11.1b
from flask import Flask, Response, render_template_string
import threading, time, json
from typing import Any

_IB=None; _TM=None

_HTML = r"""
{% raw %}
<!doctype html><title>Quant v11.1b Dashboard (Live)</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:20px}
.card{border:1px solid #ddd;border-radius:12px;padding:16px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,.05)}
h1{margin:0 0 12px}
pre{background:#111;color:#0f0;padding:12px;border-radius:10px;max-height:280px;overflow:auto}
.badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#eee;margin-right:6px}
.ok{background:#d1fae5}.err{background:#fee2e2}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;border-bottom:1px solid #eee;text-align:right}
th:first-child,td:first-child{text-align:left}
tr.g{background:#f0fff4} tr.r{background:#fff5f5}
.small{color:#555;font-size:12px}
</style>
<h1>Quant v11.1b Dashboard (Live)</h1>
<div class="card"><div class="mono">
Connected: <span id="connected" class="badge">—</span>
Market farm: <span id="market" class="badge">—</span>
HMDS farm: <span id="hmds" class="badge">—</span>
<span class="small">last update: <span id="lu">—</span></span>
</div></div>
<div class="card"><h3>Monitored Symbols</h3><div id="monitored" class="mono"></div></div>
<div class="card"><h3>Positions</h3><pre id="pos" class="mono"></pre></div>
<div class="card"><h3>PnL Summary</h3>
<table id="pnl"><thead>
<tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Last</th><th>Mkt Value</th><th>Unrealized</th><th>Realized</th></tr>
</thead><tbody></tbody></table>
</div>
<div class="card"><h3>Recent IB Messages</h3><pre id="log" class="mono"></pre></div>
<script>
function badgeClass(x){return (x===true)?'ok':(x===false)?'err':''}
const es=new EventSource('/events');
es.onmessage=(e)=>{
 const d=JSON.parse(e.data||"{}"),conn=d.conn||{},farm=d.farm||{};
 document.getElementById('connected').textContent=(conn.connected===true?'YES':(conn.connected===false?'NO':'—'));
 document.getElementById('connected').className='badge '+badgeClass(conn.connected);
 document.getElementById('market').textContent=(farm.market_ok===true?'OK':(farm.market_ok===false?'BROKEN':'—'));
 document.getElementById('market').className='badge '+badgeClass(farm.market_ok);
 document.getElementById('hmds').textContent=(farm.hmds_ok===true?'OK':(farm.hmds_ok===false?'BROKEN':'—'));
 document.getElementById('hmds').className='badge '+badgeClass(farm.hmds_ok);
 document.getElementById('lu').textContent=d.last_update?new Date(d.last_update*1000).toLocaleTimeString():'—';
 document.getElementById('monitored').textContent=(d.monitored||[]).join(', ');
 document.getElementById('pos').textContent=JSON.stringify(d.positions||{},null,2);
 const tb=document.querySelector('#pnl tbody'); tb.innerHTML='';
 (d.pnl_rows||[]).forEach(r=>{
   const tr=document.createElement('tr'); tr.className=(r.unrealized||0)>0?'g':((r.unrealized||0)<0?'r':'');
   const f=(x,n)=>(typeof x==='number')?x.toFixed(n):(x??'');
   tr.innerHTML=`<td>${r.symbol}</td><td>${r.qty}</td><td>${f(r.avg,4)}</td>
                 <td>${f(r.last,4)}</td><td>${f(r.mkt_value,2)}</td>
                 <td>${f(r.unrealized,2)}</td><td>${f(r.realized,2)}</td>`;
   tb.appendChild(tr);
 });
 document.getElementById('log').textContent=(d.tail||'').split("\n").slice(-200).join("\n");
};
</script>
{% endraw %}
"""

_LOG_TAIL=[]
def dashboard_log(msg:str)->None:
    try:
        _LOG_TAIL.append(msg)
        if len(_LOG_TAIL)>500: del _LOG_TAIL[:len(_LOG_TAIL)-500]
    except Exception: pass

def _safe_get(obj:Any, dotted:str, default=None):
    cur=obj
    for part in dotted.split('.'):
        try:
            if isinstance(cur,dict): cur=cur.get(part,default)
            else: cur=getattr(cur,part)
        except Exception: return default
    return cur

def _snapshot():
    positions,details,last_update={}, {}, None
    lock=getattr(_IB,'_lock',None)
    if lock:
        try: lock.acquire(timeout=0.2)
        except Exception: lock=None
    try:
        positions=dict(getattr(_IB,'positions',{}))
        details=dict(getattr(_IB,'pos_details',{}))
        last_update=getattr(_IB,'last_update',None)
    finally:
        if lock:
            try: lock.release()
            except Exception: pass
    pnl_rows=[{'symbol':sym,'qty':d.get('position'),'avg':d.get('averageCost'),
               'last':d.get('marketPrice'),'mkt_value':d.get('marketValue'),
               'unrealized':d.get('unrealizedPNL'),'realized':d.get('realizedPNL')} for sym,d in details.items()]
    tail=getattr(_IB,'get_log_tail',lambda:'')()
    return {'conn':{'connected':_safe_get(_IB,'conn.connected',False)},
            'farm':{'market_ok':_safe_get(_IB,'farm.market_ok',None),
                    'hmds_ok':_safe_get(_IB,'farm.hmds_ok',None)},
            'positions':positions,'monitored':sorted(list(_safe_get(_TM,'monitoring',set()) or [])),
            'pnl_rows':pnl_rows,'last_update':last_update,'tail':tail}

def start_dashboard(ib,trade_manager,host='0.0.0.0',port=8765,heartbeat_sec=1.0):
    global _IB,_TM; _IB, _TM = ib, trade_manager
    app=Flask(__name__)
    @app.route('/')
    def index(): return render_template_string(_HTML)
    @app.route('/events')
    def events():
        def gen():
            last_sig=None
            while True:
                snap=_snapshot()
                sig=(snap.get('last_update'), len(snap.get('positions') or {}))
                if sig!=last_sig:
                    yield 'data: '+json.dumps(snap)+'\n\n'
                    last_sig=sig
                time.sleep(heartbeat_sec)
        return Response(gen(), mimetype='text/event-stream')
    t=threading.Thread(target=lambda: app.run(host=host,port=port,debug=False,threaded=True),daemon=True); t.start(); return t
