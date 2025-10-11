
# main.py — QTrade v14
import os
import time
import logging
from time import monotonic
from datetime import datetime

from config import (
    ENV, DRY_RUN, HEARTBEAT_SEC,
    DASHBOARD_HOST, DASHBOARD_PORT
)
from trade_manager import TradeManager
from dashboard_server import start_dashboard
from state_bus import STATE  # Singleton state store used by dashboard

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HB_EVERY_SEC = 60  # emit heartbeat once per minute

def format_hhmmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def main():
    logging.info(f"Booting QTrade v14 ENV={ENV} DRY_RUN={DRY_RUN}")
    start_dashboard(DASHBOARD_HOST, DASHBOARD_PORT)
    logging.info(f"Dashboard at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

    tm = TradeManager(dry_run=bool(DRY_RUN))
    tm.start()

    loop_period = max(0.5, float(HEARTBEAT_SEC))
    t0_wall = time.time()
    last_hb_mono = monotonic() - HB_EVERY_SEC
    hb_seq = 0

    try:
        while True:
            loop_start = monotonic()
            tm.heartbeat()

            metrics = tm.metrics()
            STATE.update(
                env=ENV,
                dry_run=bool(DRY_RUN),
                ib_connected=metrics.get("ib_connected", False),
                pnl_today=metrics.get("pnl_today", 0.0),
                open_orders=metrics.get("open_orders", 0),
                positions=metrics.get("positions", []),
                prices=metrics.get("prices", {}),
                ema8=metrics.get("ema8", {}),
                ema21=metrics.get("ema21", {}),
                subs_symbols=set(metrics.get("subscriptions", []))
            )

            now_mono = monotonic()
            if now_mono - last_hb_mono >= HB_EVERY_SEC:
                last_hb_mono = now_mono
                hb_seq += 1
                uptime_s = int(time.time() - t0_wall)

                last_tick_at = metrics.get("last_tick_at")
                last_pos_sync_at = metrics.get("last_pos_sync_at")

                last_tick_age = None if not last_tick_at else max(0, int(time.time() - last_tick_at))
                last_pos_age = None if not last_pos_sync_at else max(0, int(time.time() - last_pos_sync_at))

                loop_lag_ms = int((monotonic() - loop_start) * 1000)

                STATE.update_heartbeat(
                    seq=hb_seq,
                    ts=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    uptime_s=uptime_s,
                    last_tick_age_s=last_tick_age,
                    last_pos_sync_age_s=last_pos_age,
                    subs=len(metrics.get("subscriptions", [])),
                    prices=len(metrics.get("prices", {})),
                    ib_connected=metrics.get("ib_connected", False),
                    live_mode=(not bool(DRY_RUN)),
                    dry_run=bool(DRY_RUN),
                    loop_lag_ms=loop_lag_ms,
                )
                logging.info(
                    "HB #%s | up=%s | subs=%d | prices=%d | tick_age=%ss | pos_age=%ss | ib=%s | live=%s | lag=%dms",
                    hb_seq, format_hhmmss(uptime_s),
                    len(metrics.get("subscriptions", [])),
                    len(metrics.get("prices", {})),
                    "-" if last_tick_age is None else last_tick_age,
                    "-" if last_pos_age is None else last_pos_age,
                    metrics.get("ib_connected", False),
                    not bool(DRY_RUN),
                    loop_lag_ms,
                )

            # loop pacing
            sleep_left = loop_period - (monotonic() - loop_start)
            if sleep_left > 0:
                time.sleep(sleep_left)

    except KeyboardInterrupt:
        logging.warning("Shutting down (Ctrl-C)")
    finally:
        try:
            tm.stop()
        except Exception as e:
            logging.error("TradeManager stop error: %s", e)

if __name__ == "__main__":
    main()
