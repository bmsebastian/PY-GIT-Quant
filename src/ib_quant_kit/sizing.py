NOTIONAL_CAPS = {
  'FUT:ES': 50000,   # example caps; adjust per your policy
  'FUT:MES': 25000,
  'STK:*': 25000,
  'ETF:*': 30000,
}
def notional_cap(symbol, asset_class):
    key = f'{asset_class}:{symbol.split()[0] if asset_class=="FUT" else "*"}'
    return NOTIONAL_CAPS.get(key, 10000)
