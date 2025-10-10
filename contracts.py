from ib_client import Stock

def qualify_contract(ib, symbol: str):
    # For now, just return a SMART stock contract; ib_client.qualify_stock() can be used later
    return Stock(symbol, exchange="SMART", currency="USD")
