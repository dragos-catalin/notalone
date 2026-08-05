from pathlib import Path
import numpy as np

from pulsarnet.observations import (
    DynamicSpectrum,
    extract_pulse_train,
    load_hdf5_dynamic_spectrum,
    load_sigproc_filterbank,
    write_sigproc_filterbank,
)


def synthetic_spectrum() -> tuple[DynamicSpectrum, float]:
    rng = np.random.default_rng(44)
    period_s = 0.1
    tsamp = 0.001
    period_samples = int(period_s / tsamp)
    n_pulses = 80
    nchan = 16
    data = rng.normal(10.0, 0.8, (n_pulses * period_samples, 1, nchan)).astype(np.float32)
    profile = np.exp(-0.5 * ((np.arange(period_samples) - 31) / 2.2) ** 2)
    amplitudes = rng.lognormal(0.0, 0.25, n_pulses)
    for pulse, amp in enumerate(amplitudes):
        start = pulse * period_samples
        data[start : start + period_samples, 0, :] += profile[:, None] * amp * 5.0
    data[:, 0, 3] += rng.normal(0, 15, data.shape[0])  # obvious RFI channel
    freqs = np.linspace(1450e6, 1350e6, nchan)
    return DynamicSpectrum(data, tsamp, freqs, source_id="TEST-PULSAR", start_mjd=60000.0), period_s


def test_hdf5_roundtrip_and_extract(tmp_path: Path) -> None:
    spectrum, period = synthetic_spectrum()
    path = tmp_path / "test.h5"
    spectrum.save_hdf5(path)
    loaded = load_hdf5_dynamic_spectrum(path)
    assert loaded.data.shape == spectrum.data.shape
    assert np.allclose(loaded.frequencies_hz, spectrum.frequencies_hz)
    train = extract_pulse_train(loaded, period_s=period)
    assert train.n_pulses >= 70
    assert np.std(train.amplitude) > 0.05
    assert abs(np.median(train.arrival_residual_s)) < 0.01


def test_sigproc_roundtrip_and_extract(tmp_path: Path) -> None:
    spectrum, period = synthetic_spectrum()
    path = tmp_path / "test.fil"
    write_sigproc_filterbank(path, spectrum)
    loaded = load_sigproc_filterbank(path)
    assert loaded.data.shape == spectrum.data.shape
    assert loaded.source_id == spectrum.source_id
    assert np.allclose(loaded.frequencies_hz, spectrum.frequencies_hz)
    train = extract_pulse_train(loaded, period_s=period)
    assert train.n_pulses >= 70
