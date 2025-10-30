from alpha_factory.cost_model import write_cost_snapshot, CostModel


def test_cost_model_roundtrip(tmp_path):
    outdir = tmp_path / "cost"
    outdir.mkdir()

    latest_path = write_cost_snapshot(
        out_dir=outdir,
        symbol="EURUSD",
        liquidity_band="THIN",
        cost_multiplier=0.6,
        note="spread slightly wide",
    )

    assert latest_path.exists()

    cm = CostModel.load_latest(outdir)
    m = cm.get_multiplier_for_trade(symbol="EURUSD", context=None)

    assert 0.59 <= m <= 0.61
