
from ib_quant_kit.sim.orderbook import L1, simulate_limit
if __name__ == "__main__":
    book = L1(bid=99.9, ask=100.1, bid_size=500, ask_size=800)
    print("Cross fill:", simulate_limit("BUY", 10, 100.2, book, 1.0))
    print("Partial fill:", simulate_limit("BUY", 100, 100.0, book, 5.0))
