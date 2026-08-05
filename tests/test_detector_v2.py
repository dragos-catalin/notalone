import numpy as np

from pulsarnet.benchmark import _inject_family
from pulsarnet.detector import benjamini_hochberg, scan_pulse_train
from pulsarnet.simulator import simulate_natural_pulsar


def test_polarization_only_protocol_is_detectable() -> None:
    natural = simulate_natural_pulsar(n_pulses=12000, seed=101)
    injected = _inject_family(natural, "polarization", seed=102)
    report = scan_pulse_train(injected, surrogate_count=96, seed=103)
    assert report.best_channel == "polarization"
    assert report.compression_gain_bits > 100
    assert report.verdict in {"candidate_structured_modulation", "interesting_but_inconclusive"}


def test_bh_q_values_are_monotonic_by_rank() -> None:
    p = [0.04, 0.001, 0.02, 0.8]
    q = benjamini_hochberg(p)
    order = np.argsort(p)
    ranked = np.asarray(q)[order]
    assert np.all(np.diff(ranked) >= -1e-12)
    assert q[1] <= q[2] <= q[3]
