
import time, json
from pathlib import Path
from rich.live import Live
from rich.table import Table
from ib_quant_kit.config import settings

def load_logs():
    p = Path(settings.data_dir) / "logs"
    rows = []
    if not p.exists(): return rows
    for fn in sorted(p.glob("*.jsonl")):
        with open(fn, "r", encoding="utf-8") as f:
            for line in f:
                try: rows.append(json.loads(line))
                except: pass
    return rows[-100:]

def render_table(rows):
    t = Table(title="Intraday Decisions & PnL")
    t.add_column("ts", no_wrap=True); t.add_column("symbol"); t.add_column("side"); t.add_column("limit"); t.add_column("oid/reason")
    for r in rows:
        t.add_row(r.get("ts",""), r.get("symbol",""), r.get("side",""), str(round(r.get("limit", 0.0), 4)), str(r.get("oid", r.get("reason",""))))
    return t

if __name__ == "__main__":
    with Live(render_table(load_logs()), refresh_per_second=2) as live:
        while True:
            time.sleep(1)
            live.update(render_table(load_logs()))


from pathlib import Path
def load_pnl():
    p = Path(settings.data_dir) / "logs" / "pnl.jsonl"
    if not p.exists(): return None
    *_, last = p.read_text(encoding="utf-8").strip().splitlines()
    import json; return json.loads(last)

def render_dashboard():
    from rich.panel import Panel
    rows = load_logs()
    pnl = load_pnl()
    t = render_table(rows)
    if pnl:
        from rich.table import Table
        pt = Table(title="PnL snapshot")
        pt.add_column("realized"); pt.add_column("unrealized"); pt.add_column("net")
        pt.add_row(f"{pnl['realized']:.2f}", f"{pnl['unrealized']:.2f}", f"{pnl['net']:.2f}")
        from rich.layout import Layout
        lay = Layout()
        lay.split_column(Layout(t, ratio=3), Layout(pt, ratio=1))
        return lay
    return t

if __name__ == "__main__":
    from rich.live import Live
    with Live(render_dashboard(), refresh_per_second=2) as live:
        import time
        while True:
            time.sleep(1)
            live.update(render_dashboard())
