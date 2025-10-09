"""
Placeholder for downloading historical bars via ibapi.
Usage pattern (pseudo):
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    ...
    client.reqHistoricalData(contract, endDateTime="", durationStr="1 Y",
                             barSizeSetting="1 min", whatToShow="TRADES",
                             useRTH=1, formatDate=1)
Save to CSV for backtesting.
"""
