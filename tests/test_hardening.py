import numpy as np
import pytest

from pulsarnet.detector import _markov_surrogate, transition_matrix, robust_binary
from pulsarnet.observations import extract_pulse_train, time_sample_rfi_mask

from test_observations import synthetic_spectrum


def test_manifest_checkpoint_resume(tmp_path) -> None:
    import json, yaml
    from pulsarnet.experiment import run_manifest
    from pulsarnet.simulator import simulate_natural_pulsar

    train = simulate_natural_pulsar(n_pulses=600, seed=3, source_id="CKPT")
    npz = tmp_path / "train.npz"
    train.save_npz(str(npz))
    manifest = {
        "experiment_id": "ckpt-test",
        "seed": 42,
        "surrogate_count": 24,
        "observations": [{"id": "obs-a", "path": str(npz), "format": "npz"}],
    }
    mpath = tmp_path / "m.yaml"
    mpath.write_text(yaml.dump(manifest), encoding="utf-8")
    out = tmp_path / "run"

    r1 = run_manifest(str(mpath), output_dir=str(out), progress=False)
    ckpt = out / "obs-a" / "checkpoint.json"
    assert ckpt.exists()
    log_text = (out / "run.log").read_text(encoding="utf-8")
    assert "target scanned" in log_text

    # Second run must resume from checkpoint and produce identical results.
    r2 = run_manifest(str(mpath), output_dir=str(out), progress=False)
    assert "RESUMED" in (out / "run.log").read_text(encoding="utf-8")
    assert r1.observations[0]["target_report"]["adjusted_p_value"] == \
        r2.observations[0]["target_report"]["adjusted_p_value"]

    # Changing the seed invalidates the checkpoint.
    manifest["seed"] = 43
    mpath.write_text(yaml.dump(manifest), encoding="utf-8")
    run_manifest(str(mpath), output_dir=str(out), progress=False)
    saved = json.loads(ckpt.read_text(encoding="utf-8"))
    assert saved["key"]["case_seed"] == 43


def test_transition_matrix_vectorized_matches_counts() -> None:
    rng = np.random.default_rng(7)
    bits = (rng.random(5000) > 0.6).astype(np.uint8)
    tm = transition_matrix(bits)
    counts = np.ones((2, 2))
    for a, b in zip(bits[:-1], bits[1:]):
        counts[int(a), int(b)] += 1.0
    expected = counts / counts.sum(axis=1, keepdims=True)
    assert np.allclose(tm, expected)


def test_transition_matrix_short_inputs() -> None:
    assert np.allclose(transition_matrix(np.array([], dtype=np.uint8)), 0.5)
    assert np.allclose(transition_matrix(np.array([1], dtype=np.uint8)), 0.5)


def test_markov_surrogate_preserves_statistics() -> None:
    rng = np.random.default_rng(11)
    tm = np.array([[0.85, 0.15], [0.4, 0.6]])
    s = _markov_surrogate(150_000, tm, rng, 0)
    assert len(s) == 150_000
    assert s[0] == 0
    recovered = transition_matrix(s)
    assert np.allclose(recovered, tm, atol=0.02)


def test_markov_surrogate_degenerate_chain() -> None:
    rng = np.random.default_rng(3)
    tm = np.array([[1.0, 0.0], [0.0, 1.0]])  # absorbing states
    s = _markov_surrogate(500, tm, rng, 1)
    assert len(s) == 500
    assert set(np.unique(s)) <= {0, 1}


def test_markov_surrogate_empty() -> None:
    rng = np.random.default_rng(1)
    tm = np.array([[0.5, 0.5], [0.5, 0.5]])
    assert len(_markov_surrogate(0, tm, rng, 0)) == 0


def test_robust_binary_handles_nan_and_constant() -> None:
    x = np.array([1.0, np.nan, 1.0, np.inf, 1.0])
    bits = robust_binary(x)
    assert bits.dtype == np.uint8
    assert len(bits) == 5
    assert np.all(robust_binary(np.full(64, 3.0)) == 0)


def test_time_sample_rfi_mask_flags_broadband_bursts() -> None:
    rng = np.random.default_rng(21)
    data = rng.normal(10.0, 0.5, (2000, 1, 8)).astype(np.float32)
    data[500] += 200.0  # broadband burst across all channels
    data[1200] += 150.0
    mask = time_sample_rfi_mask(data)
    assert mask[500] and mask[1200]
    assert mask.sum() < 20


def test_extract_with_time_rfi_mitigation() -> None:
    spectrum, period = synthetic_spectrum()
    # Inject broadband RFI bursts.
    spectrum.data[100] += 300.0
    spectrum.data[4000] += 300.0
    train = extract_pulse_train(spectrum, period_s=period, time_rfi_z_threshold=8.0)
    assert train.metadata["time_rfi_flagged_fraction"] > 0
    assert train.n_pulses >= 70


def test_extract_rejects_majority_flagged() -> None:
    spectrum, period = synthetic_spectrum()
    # An absurdly low threshold flags most samples; the extractor must refuse
    # rather than silently median-replace the majority of the observation.
    with pytest.raises(ValueError, match="broadband RFI"):
        extract_pulse_train(spectrum, period_s=period, time_rfi_z_threshold=0.05)
