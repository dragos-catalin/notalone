from pulsarnet.simulator import simulate_natural_pulsar
from pulsarnet.encoding import build_frame, inject_repeated_frame
from pulsarnet.detector import scan_pulse_train, cross_node_correlation


def test_modulation_is_more_structured_than_natural() -> None:
    natural = simulate_natural_pulsar(n_pulses=12000, seed=11)
    frame = build_frame(b"HELLO")
    modulated = inject_repeated_frame(natural, frame, start=700, repeats=9, gap_pulses=73, seed=12)

    natural_report = scan_pulse_train(natural, surrogate_count=48, seed=101)
    mod_report = scan_pulse_train(modulated, surrogate_count=48, seed=101)

    assert mod_report.strongest_lag_score > natural_report.strongest_lag_score
    assert mod_report.compression_gain_bits > natural_report.compression_gain_bits
    assert mod_report.verdict in {"candidate_structured_modulation", "interesting_but_inconclusive"}


def test_cross_node_shared_structure() -> None:
    base_a = simulate_natural_pulsar(n_pulses=10000, seed=20, source_id="A")
    base_b = simulate_natural_pulsar(n_pulses=10000, seed=21, source_id="B")
    frame = build_frame(b"NETWORK")
    a = inject_repeated_frame(base_a, frame, start=1000, repeats=8, gap_pulses=61, seed=30)
    b = inject_repeated_frame(base_b, frame, start=1017, repeats=8, gap_pulses=61, seed=31)
    result = cross_node_correlation(a, b, max_lag=100)
    assert abs(abs(result["lag_pulses"]) - 17) <= 2
    assert result["normalized_correlation"] > 0.12
