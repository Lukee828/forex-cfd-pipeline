from pathlib import Path

import pandas as pd

from feature.feature_store import FeatureStore


def test_feature_store_put_get_roundtrip(tmp_path: Path):
    root = tmp_path / ".fs"
    fs = FeatureStore(root)
    df = pd.DataFrame({"x": [1, 2, 3], "y": [10.0, 20.0, 30.0]})

    k1 = fs.put("my_feats", df, params={"w": 5}, version="v1")
    assert fs.exists("my_feats", k1)

    back = fs.get("my_feats", k1)
    pd.testing.assert_frame_equal(df, back)


def test_feature_store_key_changes_with_params_and_schema(tmp_path: Path):
    fs = FeatureStore(tmp_path / ".fs")
    df = pd.DataFrame({"a": [1, 2, 3]})

    k_params1 = fs.put("f", df, params={"alpha": 1})
    k_params2 = fs.put("f", df, params={"alpha": 2})
    assert k_params1 != k_params2

    df2 = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})
    k_schema = fs.put("f", df2, params={"alpha": 1})
    assert k_schema != k_params1
