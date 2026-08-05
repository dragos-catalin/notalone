from pulsarnet.detector import scan_pulse_train
from pulsarnet.encoding import build_frame, inject_repeated_frame
from pulsarnet.framing import recover_repeated_frame
from pulsarnet.simulator import simulate_natural_pulsar


def test_recover_synthetic_payload_and_crc() -> None:
    message = b"PRIME CLOCK"
    natural = simulate_natural_pulsar(n_pulses=12000, seed=70)
    frame = build_frame(message)
    gap = 67
    modulated = inject_repeated_frame(
        natural, frame, start=800, repeats=9, gap_pulses=gap, bit_flip_rate=0.004, seed=71
    )
    report = scan_pulse_train(modulated, surrogate_count=32, seed=72)
    assert abs(report.strongest_lag - (len(frame) + gap)) <= 2
    recovered = recover_repeated_frame(
        modulated,
        channel=report.best_channel,
        frame_period=len(frame) + gap,
        min_repeats=5,
    )
    assert recovered.repeats_used >= 5
    assert recovered.stable_fraction > 0.55
    assert recovered.crc_valid
    assert recovered.decoded_payload_utf8 == message.decode()
