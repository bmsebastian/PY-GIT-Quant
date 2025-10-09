
from pathlib import Path
from ..config import settings
import json, time

def append_pnl(snap: dict, rel="logs/pnl.jsonl"):
    out = Path(settings.data_dir) / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    row = dict(snap); row["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
