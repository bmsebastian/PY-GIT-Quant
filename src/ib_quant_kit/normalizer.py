import statistics as stats

class ClassNormalizer:
    """
    Simple cross-asset z-score normalization.
    """
    def rank(self, candidates):
        by_cls = {}
        for c in candidates:
            by_cls.setdefault(c.asset_class, []).append(c)
        ranked = []
        for cls, items in by_cls.items():
            vals = [abs(i.last / max(1e-6, i.atr)) for i in items]
            mu = stats.mean(vals) if len(vals) > 1 else 0.0
            sd = stats.pstdev(vals) if len(vals) > 1 else 1.0
            for i, v in zip(items, vals):
                i._norm_score = 0.0 if sd==0 else (v - mu)/sd
                ranked.append(i)
        return sorted(ranked, key=lambda x: getattr(x, "_norm_score", 0.0), reverse=True)
