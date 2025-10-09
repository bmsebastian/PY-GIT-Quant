class Compliance:
    def __init__(self, min_price=2.0, banlist=None, whitelist=None):
        self.min_price = min_price
        self.ban = set(banlist or [])
        self.white = set(whitelist or [])
    def ok(self, c):
        if self.white and c.symbol not in self.white: return False
        if c.symbol in self.ban: return False
        if getattr(c, "last", 0.0) < self.min_price: return False
        return True
