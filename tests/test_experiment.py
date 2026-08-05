from pathlib import Path
import json

from pulsarnet.experiment import run_manifest, sha256_file
from pulsarnet.simulator import simulate_natural_pulsar
from pulsarnet.sensitivity import run_sensitivity


def test_manifest_run_produces_hashed_target_and_control(tmp_path: Path) -> None:
    train = simulate_natural_pulsar(n_pulses=1200, seed=801, source_id="TEST-MANIFEST")
    input_path = tmp_path / "input.npz"
    train.save_npz(str(input_path))
    manifest = {
        "experiment_id": "unit-test",
        "seed": 802,
        "surrogate_count": 24,
        "observations": [
            {"id": "target-a", "path": input_path.name, "format": "npz", "control_block_size": 32}
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_manifest(manifest_path, output_dir=tmp_path / "run")
    observation = result.observations[0]
    assert observation["input_sha256"] == sha256_file(input_path)
    assert observation["controls"][0]["control_type"] == "block_permutation"
    assert Path(tmp_path / "run" / "experiment-report.json").exists()


def test_sensitivity_includes_zero_strength_control(tmp_path: Path) -> None:
    train = simulate_natural_pulsar(n_pulses=1800, seed=901, source_id="TEST-SENS")
    result = run_sensitivity(
        train,
        channel="amplitude",
        strengths_sigma=[0.0, 1.0],
        trials_per_strength=1,
        surrogate_count=24,
        seed=902,
        output=tmp_path / "sensitivity.json",
    )
    assert len(result.points) == 2
    assert result.points[0]["strength_sigma"] == 0.0
    assert (tmp_path / "sensitivity.json").exists()
