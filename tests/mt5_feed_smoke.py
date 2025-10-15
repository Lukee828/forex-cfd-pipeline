from alpha_factory.datafeeds.mt5_feed import MT5

api = MT5()
print("TICK XAUUSD", api.tick("XAUUSD"))
print("TICK US30", api.tick("US30"))
print("TICK DE40", api.tick("DE40"))
df = api.copy_rates_df("XAUUSD", timeframe="M5", count=20)
print("RATES SHAPE", df.shape)
