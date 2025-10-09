
from typing import Dict, Tuple
from ibapi.contract import Contract
class Subscriptions:
    def __init__(self): self._subs: Dict[int, Tuple[str, Contract, str]] = {}
    def add(self, reqId: int, kind: str, contract: Contract, genericTicks: str = ""):
        self._subs[reqId] = (kind, contract, genericTicks)
    def items(self): return list(self._subs.items())
    def clear(self): self._subs.clear()
subscriptions = Subscriptions()
