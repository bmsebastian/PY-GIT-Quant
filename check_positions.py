from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=20)

positions = ib.positions()
print(f'Found {len(positions)} positions:\n')

for p in positions:
    c = p.contract
    print(f'Symbol: {c.symbol}')
    print(f'LocalSymbol: {c.localSymbol}')
    print(f'SecType: {c.secType}')
    print(f'LastTrade: {c.lastTradeDateOrContractMonth}')
    print(f'ConId: {c.conId}')
    print(f'Exchange: {c.exchange}')
    print(f'Qty: {p.position}, Avg: {p.avgCost}')
    print('=' * 40)

ib.disconnect()