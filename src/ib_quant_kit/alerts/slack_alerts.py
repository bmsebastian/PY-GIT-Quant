
import json, urllib.request
from ..config import settings

def send_slack(text: str):
    url = (getattr(settings, "slack_webhook_url", None) or None) or None
    # allow reading from env directly to avoid pydantic change
    import os
    if url is None:
        url = os.getenv("SLACK_WEBHOOK_URL")
    if not url: 
        return False, "no_webhook"
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True, resp.read().decode("utf-8")
    except Exception as e:
        return False, str(e)
