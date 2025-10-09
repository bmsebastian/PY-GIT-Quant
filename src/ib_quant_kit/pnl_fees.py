from collections import defaultdict

class PnLTracker:
    """
    Tracks fees via commissionReport and exposes a simple net PnL snapshot.
    Expects ib_client to expose: on_commission_report(callback)
    """
    def __init__(self, ib_client):
        self.realized = 0.0
        self.unrealized = 0.0
        self.fees = 0.0
        self._by_perm = defaultdict(float)
        ib_client.on_commission_report(self._on_commission)

    def _on_commission(self, report):
        try:
            self.fees += float(report.commission)
        except Exception:
            pass

    def snapshot(self):
        return dict(realized=self.realized, unrealized=self.unrealized, fees=self.fees)
