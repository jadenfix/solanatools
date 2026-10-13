import math
import os
from pathlib import Path
import pytest
import main as main_module
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


def test_output_cannot_overwrite_input_csv(tmp_path):
    source = tmp_path / "prices.csv"
    original = b"timestamp,price\nt0,10\nt1,9\n"
    source.write_bytes(original)
    with pytest.raises(SystemExit) as error:
        main(["--csv", str(source), "--period", "1", "--output", str(source)])
    assert error.value.code == 2
    assert source.read_bytes() == original


@pytest.mark.parametrize("alias_kind", ["symlink", "hardlink"])
def test_output_alias_cannot_overwrite_input_csv(tmp_path, alias_kind):
    source = tmp_path / "prices.csv"
    alias = tmp_path / "result.json"
    original = b"timestamp,price\nt0,10\nt1,9\n"
    source.write_bytes(original)
    try:
        if alias_kind == "symlink":
            alias.symlink_to(source)
        else:
            os.link(source, alias)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"{alias_kind} unavailable: {error}")
    with pytest.raises(SystemExit) as error:
        main(["--csv", str(source), "--period", "1", "--output", str(alias)])
    assert error.value.code == 2
    assert source.read_bytes() == original


@pytest.mark.parametrize("alias_kind", ["exact", "symlink", "hardlink"])
def test_demo_output_cannot_overwrite_bundled_fixture(tmp_path, monkeypatch, alias_kind):
    fixture = tmp_path / "fixtures" / "synthetic_prices.csv"
    fixture.parent.mkdir()
    original = (Path(main_module.__file__).parent / "fixtures" / "synthetic_prices.csv").read_bytes()
    fixture.write_bytes(original)
    monkeypatch.setattr(main_module, "__file__", str(tmp_path / "main.py"))
    output = fixture if alias_kind == "exact" else tmp_path / "replay.json"
    try:
        if alias_kind == "symlink":
            output.symlink_to(fixture)
        elif alias_kind == "hardlink":
            os.link(fixture, output)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"{alias_kind} unavailable: {error}")
    with pytest.raises(SystemExit) as error:
        main_module.main(["--demo", "--output", str(output)])
    assert error.value.code == 2
    assert fixture.read_bytes() == original


def test_failed_atomic_replace_preserves_existing_output(tmp_path, monkeypatch):
    output = tmp_path / "replay.json"
    output.write_text("previous output\n")

    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("main.os.replace", fail_replace)
    with pytest.raises(SystemExit) as error:
        main(["--demo", "--output", str(output)])
    assert error.value.code == 2
    assert output.read_text() == "previous output\n"
    assert list(tmp_path.glob(".replay.json.*.tmp")) == []
