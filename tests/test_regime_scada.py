import numpy as np
import pandas as pd
import pytest

from pumpguard.datasets.scada import (
    ChannelSpec,
    ScadaError,
    ScadaSchema,
    load_scada_csv,
    time_block_split,
)
from pumpguard.orders import rpm_from_supply_frequency
from pumpguard.regime import (
    flow_speed_grid,
    illustrative_esp,
    illustrative_well,
    naive_affinity_projection,
    speed_sweep,
)

SPEEDS = [rpm_from_supply_frequency(f) for f in (30, 40, 45, 50, 55, 60)]

# ------------------------------------------------------------------- regime


def test_speed_sweep_is_consistent_and_flags_infeasible_speeds():
    df = speed_sweep(illustrative_esp(), illustrative_well(), SPEEDS, n_vanes=7)
    assert df["synthetic"].all()
    assert not df.loc[0, "feasible"]
    assert "cannot reach" in df.loc[0, "note"]
    ok = df[df["feasible"]]
    assert np.all(np.diff(ok["flow_m3_s"]) > 0)
    assert np.all(np.diff(ok["intake_pressure_pa"]) < 0)
    assert ok["vane_pass_hz"].iloc[-1] == pytest.approx(7 * 60.0)
    assert ok["in_operating_range"].iloc[-1]


def test_flow_speed_grid_obeys_affinity_and_power_identity():
    pump = illustrative_esp()
    grid = flow_speed_grid(pump, [3000.0, 3600.0], flow_fractions=(0.0, 0.5, 1.0))
    assert len(grid) == 6
    a = grid[grid["speed_rpm"] == 3000.0].reset_index(drop=True)
    b = grid[grid["speed_rpm"] == 3600.0].reset_index(drop=True)
    r = 3600.0 / 3000.0
    np.testing.assert_allclose(b["flow_m3_s"], a["flow_m3_s"] * r, rtol=1e-12)
    np.testing.assert_allclose(b["head_m"], a["head_m"] * r**2, rtol=1e-10)
    np.testing.assert_allclose(b["hydraulic_power_w"], a["hydraulic_power_w"] * r**3, rtol=1e-10)
    np.testing.assert_allclose(b["relative_flow"], a["relative_flow"], rtol=1e-12)
    with pytest.raises(ValueError, match="flow_fractions"):
        flow_speed_grid(pump, [3000.0], flow_fractions=(1.5,))


def test_naive_projection_violates_the_system_curve_away_from_reference():
    ref = rpm_from_supply_frequency(50)
    df = naive_affinity_projection(illustrative_esp(), illustrative_well(), ref, SPEEDS)
    at_ref = df[df["speed_rpm"] == ref].iloc[0]
    assert at_ref["system_head_gap_m"] == pytest.approx(0.0, abs=1e-6)
    assert at_ref["flow_error_pct"] == pytest.approx(0.0, abs=1e-9)
    at_60 = df[df["speed_rpm"] == rpm_from_supply_frequency(60)].iloc[0]
    assert abs(at_60["system_head_gap_m"]) > 50.0  # naive point is not a physical operating point
    assert abs(at_60["flow_error_pct"]) > 10.0
    assert "note" in df.columns  # 30 Hz is infeasible for the consistent model


def test_no_cavitation_classification_anywhere_in_benchmark_labels():
    from pumpguard.datasets.paderborn import LABELS

    assert not any("cavitation" in label for label in LABELS)


# --------------------------------------------------------------------- scada


def _write_scada(path, n=3 * 1440, interval_s=60, start="2026-04-01", **edits):
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "Time": pd.date_range(start, periods=n, freq=f"{interval_s}s").strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "Pi": rng.normal(27.95, 0.5, n),
            "Pd": rng.normal(103.47, 0.5, n),
            "Ti": rng.normal(63.45, 0.01, n),
            "Vx": rng.normal(0.12, 0.001, n),
            "Freq": np.full(n, 44.0),
        }
    )
    for key, fn in edits.items():
        df = fn(df) if key == "transform" else df
    df.to_csv(path, index=False)
    return path


SCHEMA = ScadaSchema(
    time_column="Time",
    channels=(
        ChannelSpec("Pi", "intake_pressure", "pressure", "bar"),
        ChannelSpec("Pd", "discharge_pressure", "pressure", "bar"),
        ChannelSpec("Ti", "intake_temperature", "temperature", "degC"),
        ChannelSpec("Vx", "vibration_x", "acceleration", "g"),
        ChannelSpec("Freq", "drive_frequency", "frequency", "Hz"),
    ),
    expected_interval_s=60.0,
)


def test_load_scada_converts_to_si_and_reports(tmp_path):
    data, report = load_scada_csv(_write_scada(tmp_path / "s.csv"), SCHEMA)
    expected = ["time", "intake_pressure", "discharge_pressure", "intake_temperature",
                "vibration_x", "drive_frequency"]  # fmt: skip
    assert list(data.columns) == expected
    assert data["intake_pressure"].mean() == pytest.approx(27.95e5, rel=0.01)
    assert data["vibration_x"].mean() == pytest.approx(0.12 * 9.80665, rel=0.01)
    assert report["sample_rate_hz"] == pytest.approx(1 / 60)
    assert report["units"]["intake_pressure"] == "Pa"
    assert report["logged_units"]["intake_pressure"] == "bar"
    assert report["n_gaps"] == 0


def test_unit_conversions_for_other_logged_units():
    from pumpguard.datasets.scada import UNITS

    s = pd.Series([0.0, 100.0])
    np.testing.assert_allclose(UNITS["temperature"]["K"][1](s), [-273.15, -173.15])
    np.testing.assert_allclose(UNITS["temperature"]["degF"][1](pd.Series([32.0, 212.0])), [0, 100])
    np.testing.assert_allclose(UNITS["flow"]["bpd"][1](pd.Series([86_400.0])), [0.158987294928])
    np.testing.assert_allclose(UNITS["dimensionless"]["%"][1](pd.Series([45.1])), [0.451])


def test_scada_validation_errors(tmp_path):
    path = _write_scada(tmp_path / "s.csv")
    with pytest.raises(ScadaError, match="missing column"):
        load_scada_csv(path, ScadaSchema("Time", (ChannelSpec("Tm", "tm", "temperature", "degC"),)))
    with pytest.raises(ScadaError, match="differs from the declared"):
        load_scada_csv(path, ScadaSchema("Time", SCHEMA.channels, expected_interval_s=1.0))
    with pytest.raises(ScadaError, match="unit 'atm'"):
        ChannelSpec("Pi", "pi", "pressure", "atm")
    with pytest.raises(ScadaError, match="unknown quantity"):
        ChannelSpec("Pi", "pi", "loudness", "dB")
    with pytest.raises(ScadaError, match="identifier"):
        ChannelSpec("Pi", "intake pressure", "pressure", "bar")
    with pytest.raises(ScadaError, match="unique"):
        ScadaSchema("Time", (SCHEMA.channels[0], SCHEMA.channels[0]))
    with pytest.raises(ScadaError, match="at least one"):
        ScadaSchema("Time", ())
    with pytest.raises(ScadaError, match="tolerance"):
        ScadaSchema("Time", SCHEMA.channels, interval_tolerance=2.0)
    with pytest.raises(ScadaError, match="expected_interval_s"):
        ScadaSchema("Time", SCHEMA.channels, expected_interval_s=-1.0)


def test_nonfinite_values_raise_or_are_dropped_and_reported(tmp_path):
    def corrupt(df):
        df["Pi"] = df["Pi"].astype(object)
        df.loc[5, "Pi"] = "ERR"
        df.loc[9, "Pd"] = np.nan
        return df

    path = _write_scada(tmp_path / "bad.csv", transform=corrupt)
    with pytest.raises(ScadaError, match="2 row"):
        load_scada_csv(path, SCHEMA)
    data, report = load_scada_csv(path, SCHEMA, drop_nonfinite=True)
    assert report["n_rows_dropped_nonfinite"] == 2
    assert np.isfinite(data.drop(columns="time").to_numpy()).all()


def test_duplicates_unsorted_rows_and_gaps(tmp_path):
    def mess(df):
        df = pd.concat([df.iloc[:10], df.iloc[[3]], df.iloc[400:]])  # duplicate + 6.5 h gap
        return df.iloc[::-1]  # reversed order

    data, report = load_scada_csv(_write_scada(tmp_path / "m.csv", transform=mess), SCHEMA)
    assert data["time"].is_monotonic_increasing
    assert report["n_duplicate_timestamps_dropped"] == 1
    assert report["n_gaps"] == 1
    assert report["largest_gap_s"] == pytest.approx(391 * 60)


def test_bad_time_column_and_too_few_rows(tmp_path):
    def bad_time(df):
        df["Time"] = "not a date"
        return df

    with pytest.raises(ScadaError, match="parse time"):
        load_scada_csv(_write_scada(tmp_path / "t.csv", transform=bad_time), SCHEMA)
    with pytest.raises(ScadaError, match="fewer than two"):
        load_scada_csv(_write_scada(tmp_path / "one.csv", n=1), SCHEMA)


def test_time_block_split_never_shares_a_day_and_honours_embargo(tmp_path):
    data, _ = load_scada_csv(_write_scada(tmp_path / "s.csv", n=10 * 1440), SCHEMA)
    train, test = time_block_split(data, test_fraction=0.2)
    train_days = set(train["time"].dt.floor("1D"))
    test_days = set(test["time"].dt.floor("1D"))
    assert train_days.isdisjoint(test_days)
    assert len(test_days) == 2
    assert max(train_days) < min(test_days)  # chronological hold-out
    train_e, _ = time_block_split(data, test_fraction=0.2, embargo_blocks=1)
    assert len(set(train_e["time"].dt.floor("1D"))) == 7  # the day before the test block dropped
    r1 = time_block_split(data, mode="random", seed=3)[1]
    r2 = time_block_split(data, mode="random", seed=3)[1]
    pd.testing.assert_frame_equal(r1, r2)


def test_time_block_split_validation(tmp_path):
    data, _ = load_scada_csv(_write_scada(tmp_path / "s.csv", n=2 * 1440), SCHEMA)
    with pytest.raises(ValueError, match="test_fraction"):
        time_block_split(data, test_fraction=1.5)
    with pytest.raises(ValueError, match="mode"):
        time_block_split(data, mode="shuffle")
    with pytest.raises(ValueError, match="embargo"):
        time_block_split(data, embargo_blocks=-1)
    one_day = data[data["time"] < pd.Timestamp("2026-04-02")]
    with pytest.raises(ValueError, match="two time blocks"):
        time_block_split(one_day)
