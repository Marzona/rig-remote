import configparser
import itertools
from pathlib import Path

import pytest


def generate_test_configs(output_dir: str | Path) -> list[Path]:
    """Generate INI fixtures covering all parameter combinations.

    Boolean fields alternate per sgn_level index so content varies without
    duplicating filenames.  Returns the list of files written.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    passes_values    = [1, 200, 400]
    interval_values  = [1, 5, 10]
    delay_values     = [1, 10, 20]
    sgn_level_values = [-100, -30, 0, 100]

    written: list[Path] = []
    for idx, (p, i, d, s) in enumerate(itertools.product(
        passes_values, interval_values, delay_values, sgn_level_values,
    )):
        b = idx % 2 == 0   # alternate True/False so content varies

        config = configparser.ConfigParser()
        config["Scanning"] = {
            "passes":        str(p),
            "aggr_scan":     str(b).lower(),
            "auto_bookmark": str(not b).lower(),
            "range_min":     "24,000",
            "range_max":     "1800,000",
            "interval":      str(i),
            "delay":         str(d),
            "record":        str(b).lower(),
            "sgn_level":     str(s),
            "wait":          str(not b).lower(),
        }
        config["Main"] = {
            "log_filename":    "none",
            "save_exit":       str(b).lower(),
            "always_on_top":   str(not b).lower(),
            "log":             str(b).lower(),
            "bookmark_filename": "./test/test_files/test-bookmarks.csv",
        }
        config["Rig URI"] = {
            "hostname1": "127.0.0.1",
            "hostname2": "127.0.0.1",
            "port1":     "7356",
            "port2":     "7357",
        }
        config["Monitor"] = {}

        file_path = output_path / f"test-config_{p}_{i}_{d}_{s}.ini"
        with open(file_path, "w", encoding="utf-8") as fh:
            config.write(fh)
        written.append(file_path)

    return written


# ---------------------------------------------------------------------------
# pytest tests — tmp_path is cleaned up automatically after each test
# ---------------------------------------------------------------------------

_EXPECTED_FILE_COUNT = 3 * 3 * 3 * 4   # passes × interval × delay × sgn_level


def test_generate_test_configs_produces_correct_file_count(tmp_path):
    """Generator writes exactly one file per parameter combination."""
    written = generate_test_configs(tmp_path)
    assert len(written) == _EXPECTED_FILE_COUNT, (
        f"Expected {_EXPECTED_FILE_COUNT} files, got {len(written)}"
    )


def test_generate_test_configs_all_files_are_valid_ini(tmp_path):
    """Every generated file is parseable and contains the required sections."""
    written = generate_test_configs(tmp_path)
    for path in written:
        cfg = configparser.ConfigParser()
        cfg.read(str(path))
        assert "Scanning" in cfg, f"{path.name}: missing [Scanning] section"
        assert "Main"     in cfg, f"{path.name}: missing [Main] section"
        assert "Rig URI"  in cfg, f"{path.name}: missing [Rig URI] section"


def test_generate_test_configs_filenames_encode_parameters(tmp_path):
    """File names follow the test-config_<passes>_<interval>_<delay>_<sgn>.ini
    convention and are unique across all combinations."""
    written = generate_test_configs(tmp_path)
    names = [p.name for p in written]
    assert len(names) == len(set(names)), "Duplicate filenames detected"
    for name in names:
        assert name.startswith("test-config_"), f"Unexpected filename: {name}"
        assert name.endswith(".ini")


# ---------------------------------------------------------------------------
# Script entry-point — regenerates the committed fixtures in test_config_files/
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    target = Path(__file__).parent / "test_config_files"
    written = generate_test_configs(target)
    print(f"Regenerated {len(written)} fixtures in {target}")
