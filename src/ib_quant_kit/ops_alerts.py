class Notifier:
    """
    Minimal notifier. Defaults to stdout.
    """
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url
    def send(self, title, body):
        print(f"[ALERT] {title}: {body}")
