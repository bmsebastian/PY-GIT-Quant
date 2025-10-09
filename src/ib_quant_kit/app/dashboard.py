import os, threading, time
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from ..config import settings
from ..console import console
from ..state_api import get_positions, get_orders, get_risk, get_pnl, get_circuit, set_kill_switch, get_pnl_symbols, get_blotter

app = Flask(__name__, template_folder="templates", static_folder="static")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/positions")
def api_positions():
    return jsonify(get_positions())

@app.get("/api/orders")
def api_orders():
    return jsonify(get_orders())

@app.get("/api/risk")
def api_risk():
    return jsonify(get_risk())

@app.get("/api/pnl")
def api_pnl():
    return jsonify(get_pnl())

@app.get("/api/circuit")
def api_circuit():
    return jsonify(get_circuit())

def run():
    host = os.getenv("DASH_HOST", "127.0.0.1")
    port = int(os.getenv("DASH_PORT", "8080"))
    debug = os.getenv("DASH_DEBUG", "0") == "1"
    console.log(f"[bold green]Dashboard listening[/] http://{host}:{port}")
    import threading
    t = threading.Thread(target=_push_loop, daemon=True)
    t.start()
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=False)

if __name__ == "__main__":
    run()


@app.post("/api/kill")
def api_kill():
    # Guard: only allow in DRY_RUN mode to avoid accidental live-wire misuse
    dry = os.getenv("DRY_RUN", "1") == "1"
    if not dry:
        return jsonify({"ok": False, "error": "Kill-switch is only enabled in DRY_RUN=1 for safety."}), 403
    try:
        want_kill = os.getenv("KILL_ON", "1") == "1"  # optional env default
        # Toggle based on current circuit state
        cur = get_circuit()
        target = not cur.get("trading_enabled", True)
        # If you want explicit control, you can pass ?on=1/0 later; keeping simple toggle now
        ok = set_kill_switch(on=target, reason="dashboard")
        return jsonify({"ok": bool(ok), "trading_enabled": not target})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/pnl_symbols")
def api_pnl_symbols():
    return jsonify(get_pnl_symbols())

@app.get("/api/blotter")
def api_blotter():
    try:
        limit = int(os.getenv("BLOTTER_LIMIT", "100"))
    except Exception:
        limit = 100
    from flask import request
    qlimit = request.args.get("limit")
    if qlimit and qlimit.isdigit():
        limit = int(qlimit)
    return jsonify(get_blotter(limit))

def _push_loop():
    import time
    while True:
        try:
            payload = {
                "positions": get_positions(),
                "orders": get_orders(),
                "risk": get_risk(),
                "pnl": get_pnl(),
                "pnl_symbols": get_pnl_symbols(),
                "circuit": get_circuit(),
                "blotter": get_blotter(50),
            }
            socketio.emit("update", payload, namespace="/stream")
        except Exception as e:
            console.log(f"[bold yellow]Push loop error[/]: {e}")
        time.sleep(2)

@socketio.on("connect", namespace="/stream")
def on_connect():
    # Send immediate snapshot
    payload = {
        "positions": get_positions(),
        "orders": get_orders(),
        "risk": get_risk(),
        "pnl": get_pnl(),
        "pnl_symbols": get_pnl_symbols(),
        "circuit": get_circuit(),
        "blotter": get_blotter(50),
    }
    socketio.emit("update", payload, namespace="/stream")

