from src.alpha_factory import registry
import pandas as pd


def main():
    s = pd.Series(range(200), dtype=float)
    names = sorted(registry.names())
    print("Available factors:", names)
    for name in names:
        f = registry.make(name)
        sig = f.compute(s)
        print(name, list(sig.iloc[-5:]))


if __name__ == "__main__":
    main()
