from pathlib import Path
from pulsarnet.simulator import simulate_natural_pulsar
from pulsarnet.models import PulseTrain


def test_pulse_train_metadata_roundtrip(tmp_path: Path) -> None:
    train = simulate_natural_pulsar(n_pulses=256, seed=42)
    train.metadata = {"dm_pc_cm3": 12.3, "labels": ["target", "test"]}
    path = tmp_path / "train.npz"
    train.save_npz(str(path))
    loaded = PulseTrain.load_npz(str(path))
    assert loaded.metadata == train.metadata
