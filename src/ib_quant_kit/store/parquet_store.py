
from pathlib import Path
import pandas as pd
from ..config import settings

def write_parquet(df: pd.DataFrame, rel_path: str):
    out = Path(settings.data_dir) / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)

def append_jsonl(records: list[dict], rel_path: str):
    out = Path(settings.data_dir) / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        for r in records:
            import json; f.write(json.dumps(r) + "\n")
