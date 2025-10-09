
from threading import Event, Lock
from typing import Dict, Tuple, List
from ibapi.contract import Contract
class ContractCache:
    def __init__(self):
        self._cache: Dict[Tuple, Contract] = {}
        self._pending: Dict[int, Event] = {}
        self._results: Dict[int, List] = {}
        self._lock = Lock(); self._next_req_id = 10000
    def next_req_id(self) -> int:
        with self._lock: self._next_req_id += 1; return self._next_req_id
    def key(self, c: Contract) -> Tuple:
        return (getattr(c,"conId",0), getattr(c,"symbol",""), getattr(c,"secType",""),
                getattr(c,"lastTradeDateOrContractMonth",""), getattr(c,"strike",0.0),
                getattr(c,"right",""), getattr(c,"exchange",""), getattr(c,"currency",""),
                getattr(c,"tradingClass",""))
    def get(self, c: Contract): return self._cache.get(self.key(c))
    def put(self, c: Contract): self._cache[self.key(c)] = c
    def on_contract_details(self, reqId: int, contractDetails):
        self._results.setdefault(reqId, []).append(contractDetails)
    def on_contract_details_end(self, reqId: int):
        ev = self._pending.get(reqId); ev and ev.set()
    def await_details(self, reqId: int, timeout=3.0):
        ev = Event(); self._pending[reqId] = ev; ev.wait(timeout=timeout)
        res = self._results.pop(reqId, []); self._pending.pop(reqId, None); return res
contract_cache = ContractCache()
