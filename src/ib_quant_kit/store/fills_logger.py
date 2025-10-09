import os, json, time
LOG_DIR = "./runtime"
os.makedirs(LOG_DIR, exist_ok=True)
FILLS_FILE = os.path.join(LOG_DIR, "fills.jsonl")

def append_fill(payload: dict):
    line = json.dumps({"ts": time.time(), **payload})
    with open(FILLS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
