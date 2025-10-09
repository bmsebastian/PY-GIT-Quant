from dataclasses import dataclass
from typing import List, Iterable, Dict, Optional
import time

@dataclass
class Candidate:
    symbol: str
    asset_class: str  # 'STK'|'FUT'|'ETF'
    last: float
    atr: float
    scanner_source: str  # 'IB'|'FALLBACK'

class SelectionEngine:
    """
    Live selection with IB scanner preference and cached fallback.
    Expects ib_client to expose: fetch_scanner() -> List[dict].
    """
    def __init__(self, ib_client, compliance_filter, normalizer, cache_ttl=120):
        self.ib = ib_client
        self.compliance = compliance_filter
        self.normalize = normalizer
        self._cache: Dict[str, List[Candidate]] = {}
        self._cache_ts: Dict[str, float] = {}
        self.cache_ttl = cache_ttl

    def _cache_get(self, key) -> Optional[List[Candidate]]:
        ts = self._cache_ts.get(key, 0)
        if time.time() - ts <= self.cache_ttl:
            return self._cache.get(key)
        return None

    def _cache_put(self, key, val):
        self._cache[key] = val
        self._cache_ts[key] = time.time()

    def ib_scanner(self) -> List[Candidate]:
        try:
            cands = self.ib.fetch_scanner()  # returns List[dict] with fields compatible with Candidate
            cands = [Candidate(**c, scanner_source='IB') for c in cands]
            if cands:
                self._cache_put("scan", cands)
                return cands
        except Exception:
            pass
        return self._cache_get("scan") or []

    def select(self, top_n=25) -> List[Candidate]:
        raw = self.ib_scanner()
        filt = [c for c in raw if self.compliance.ok(c)]
        scored = self.normalize.rank(filt)  # returns same items sorted by normalized score
        return scored[:top_n]
