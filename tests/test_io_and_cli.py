import json

import numpy as np
import pandas as pd
import pytest

from pumpguard import SignalConfig, __version__, simulate
from pumpguard.cli import main
from pumpguard.demo import main as demo_main
from pumpguard.io import load_signal, save_signal

# ------------------------------------------------------------------------ io


def test_save_and_load_roundtrip_with_metadata(tmp_path):
    sig = simulate(SignalConfig(condition="imbalance", duration=0.5))
    csv_path, sidecar = save_signal(tmp_path / "sub" / "s.csv", sig.t, sig.x, sig.metadata())
    assert sidecar is not None
    assert sidecar.exists()
    loaded = load_signal(csv_path)
    np.testing.assert_allclose(loaded.x, sig.x)
    assert loaded.fs == pytest.approx(12_000)
    assert loaded.metadata["synthetic"] is True


def test_metadata_with_numpy_values_is_serialised(tmp_path):
    meta = {"rpm": np.float64(1800.0), "n": np.int64(3), "arr": np.arange(3), "p": tmp_path}
    _, sidecar = save_signal(tmp_path / "np.csv", [0.0, 0.1], [1.0, 2.0], meta)
    assert json.loads(sidecar.read_text()) == {
        "rpm": 1800.0,
        "n": 3,
        "arr": [0, 1, 2],
        "p": str(tmp_path),
    }
    with pytest.raises(TypeError, match="not JSON serialisable"):
        save_signal(tmp_path / "bad.csv", [0.0, 0.1], [1.0, 2.0], {"x": object()})


def test_load_infers_fs_without_sidecar(tmp_path):
    t = np.arange(1000) / 2500.0
    save_signal(tmp_path / "plain.csv", t, np.sin(t))
    assert load_signal(tmp_path / "plain.csv").fs == pytest.approx(2500.0)


def test_load_rejects_missing_columns(tmp_path):
    pd.DataFrame({"a": [1, 2]}).to_csv(tmp_path / "bad.csv", index=False)
    with pytest.raises(ValueError, match="missing column"):
        load_signal(tmp_path / "bad.csv")


def test_load_rejects_irregular_time(tmp_path):
    save_signal(tmp_path / "irr.csv", [0.0, 0.1, 0.3, 0.35], [1.0, 2.0, 3.0, 4.0])
    with pytest.raises(ValueError, match="uniformly"):
        load_signal(tmp_path / "irr.csv")
    assert load_signal(tmp_path / "irr.csv", fs=10.0).fs == 10.0


def test_save_rejects_length_mismatch(tmp_path):
    with pytest.raises(ValueError, match="same length"):
        save_signal(tmp_path / "x.csv", [0.0, 1.0], [1.0])


# ----------------------------------------------------------------------- cli


def run(command: str, *extra: str) -> int:
    """Call the CLI with a space-separated command plus extra (path) arguments."""
    return main([*command.split(), *extra])


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        run("--version")
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_demo_writes_csv_json_png(tmp_path, capsys):
    assert run("demo --condition bearing_inner --duration 0.5 --out", str(tmp_path)) == 0
    for suffix in ("csv", "json", "png"):
        assert (tmp_path / f"bearing_inner_signal.{suffix}").exists()
    meta = json.loads((tmp_path / "bearing_inner_signal.json").read_text())
    assert meta["synthetic"] is True
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out
    assert "env_bpfi_ratio" in out


def test_legacy_module_entry_point_and_alias(tmp_path, capsys):
    argv = ["--condition", "bearing_like", "--duration", "0.5", "--no-plot", "--out"]
    assert demo_main([*argv, str(tmp_path)]) == 0
    assert "deprecated" in capsys.readouterr().err
    assert (tmp_path / "bearing_outer_signal.csv").exists()


def test_features_command_on_demo_output(tmp_path, capsys):
    run("demo --condition imbalance --duration 0.5 --no-plot --out", str(tmp_path))
    capsys.readouterr()
    assert run("features --json", str(tmp_path / "imbalance_signal.csv")) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["synthetic"] is True
    assert record["rpm"] == pytest.approx(1800)
    assert record["features"]["amp_1x"] > 0.4


def test_features_command_on_plain_csv_without_rpm(tmp_path, capsys):
    t = np.arange(2000) / 1000.0
    save_signal(tmp_path / "real.csv", t, np.sin(2 * np.pi * 25 * t))
    assert run("features", str(tmp_path / "real.csv")) == 0
    out = capsys.readouterr().out
    assert "skipped" in out
    assert "amp_1x" not in out


def test_features_command_with_custom_bearing(tmp_path, capsys):
    t = np.arange(4000) / 4000.0
    save_signal(tmp_path / "s.csv", t, np.sin(2 * np.pi * 30 * t))
    command = "features --json --rpm 1800 --n-elements 8 --ball-mm 7 --pitch-mm 34"
    assert run(command, str(tmp_path / "s.csv")) == 0
    assert "env_bpfo_ratio" in json.loads(capsys.readouterr().out)["features"]


def test_partial_custom_bearing_is_rejected():
    with pytest.raises(SystemExit) as exc:
        run("bearing --rpm 1800 --ball-mm 7")
    assert exc.value.code == 2


def test_dataset_command(tmp_path, capsys):
    out = tmp_path / "ds.csv"
    command = "dataset --conditions healthy imbalance --machines 2 --segments 2 --duration 0.2"
    assert run(command, "--out", str(out)) == 0
    assert len(pd.read_csv(out)) == 8
    assert "group_id" in capsys.readouterr().out


def test_bearing_command(capsys):
    assert run("bearing --rpm 1800") == 0
    out = capsys.readouterr().out
    assert "BPFO" in out
    assert "107.54" in out


def test_invalid_values_exit_cleanly(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        run("demo --fs 500 --rpm 9000 --out", str(tmp_path))
    assert exc.value.code == 2
    assert "alias" in capsys.readouterr().err


def test_missing_file_exits_cleanly(tmp_path):
    with pytest.raises(SystemExit) as exc:
        run("features", str(tmp_path / "missing.csv"))
    assert exc.value.code == 2
