from ib_client import IBClient

if __name__ == "__main__":
    ibc = IBClient()
    ib = ibc.connect()
    try:
        aapl = ibc.qualify_stock("AAPL")
        t = ib.reqMktData(aapl, "", False, False)
        ib.sleep(2)
        print("OK (may be None in stub): last =", getattr(t, "last", None))
    finally:
        ibc.disconnect()
