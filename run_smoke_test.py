import yaml, os
from src.exec.backtest import main as backtest_main

print('=== Smoke Test ===')
print('Repo present:', os.listdir('.'))
print('Loading config...')
print()
