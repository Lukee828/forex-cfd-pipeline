import argparse, pandas as pd, numpy as np
from pathlib import Path

def check_file(path: Path):
    issues = []
    try:
        df = pd.read_parquet(path)
    except Exception as e:
        return [f'{path.name}: cannot read ({e})']
    if not isinstance(df.index, pd.DatetimeIndex):
        issues.append(f'{path.name}: index is not DatetimeIndex')
    else:
        if df.index.tz is None:
            issues.append(f'{path.name}: index not tz-aware (expected UTC)')
        if df.index.duplicated().any():
            issues.append(f'{path.name}: duplicate timestamps found')
        if (df.index.weekday>=5).mean()>0.05:
            issues.append(f'{path.name}: >5% weekend bars (check calendar)')
    for col in ['Open','High','Low','Close']:
        if col not in df.columns: issues.append(f'{path.name}: missing {col}')
        elif df[col].isna().mean()>0:
            issues.append(f'{path.name}: NaNs in {col}')
    if 'Volume' in df.columns and df['Volume'].isna().mean()>0:
        issues.append(f'{path.name}: NaNs in Volume')
    return issues

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='data/prices_1d')
    args = ap.parse_args()
    root = Path(args.root)
    files = list(root.glob('*.parquet'))
    if not files:
        print('No parquet files in', root); return
    all_issues = []
    for f in files:
        all_issues += check_file(f)
    if all_issues:
        print('HEALTH CHECK ISSUES:')
        for x in all_issues: print('-', x)
    else:
        print('All good.')

if __name__ == '__main__':
    main()
