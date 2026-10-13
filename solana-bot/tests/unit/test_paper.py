import math
import pytest
from core.engine.paper import PaperExecutionEngine
from core.strategies.rsi_momentum import RSIMomentumStrategy
from main import main


def test_rsi_uses_exact_period_deltas_and_bounded_history():
    strategy = RSIMomentumStrategy(period=3)
    for price in [4, 3, 2]:
        strategy.next({"price": price})
    assert not strategy.get_signals()
    strategy.next({"price": 1})
    assert strategy.last_rsi == 0
    assert strategy.get_signals() == [{"direction": "LONG", "price": 1.0}]
    for price in range(1, 100):
        strategy.next({"price": price})
    assert len(strategy.prices) == 4


def test_flat_prices_are_neutral():
    strategy = RSIMomentumStrategy(period=2)
    for _ in range(10):
        strategy.next({"price": 100})
    assert strategy.last_rsi == 50
    assert not strategy.get_signals()


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_invalid_price_rejected(price):
    with pytest.raises(ValueError):
        PaperExecutionEngine(RSIMomentumStrategy()).run([{"price": price}])


def test_ledger_reconciles_cash_inventory_and_risk_exit():
    engine = PaperExecutionEngine(RSIMomentumStrategy(period=2), cash=1000,
                                  fee_bps=100, max_exposure=.25)
    result = engine.run([{"price": p} for p in [100, 99, 98, 90, 95, 100]])
    buy, sell = result["ledger"]
    assert buy["side"] == "BUY" and sell["reason"] == "STOP_LOSS"
    assert buy["quantity"] * buy["price"] + buy["fee"] == pytest.approx(250)
    assert sell["quantity"] == buy["quantity"]
    expected_cash = 1000 - 250 + sell["quantity"] * 90 - sell["fee"]
    assert result["final_equity"] == pytest.approx(expected_cash)
    assert all(p["cash"] >= 0 and p["quantity"] >= 0 for p in result["curve"])


def test_cli_runs_full_offline_fixture_and_exports(tmp_path):
    output = tmp_path / "nested" / "replay.json"
    result = main(["--demo", "--output", str(output)])
    assert result["bars"] == 75 and result["fills"] > 0
    assert output.exists()
    assert all(math.isfinite(p["equity"]) for p in result["curve"])


def test_bad_csv_fails_without_silent_success(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("price\nNaN\n")
    with pytest.raises(SystemExit) as error:
        main(["--csv", str(path)])
    assert error.value.code == 2
