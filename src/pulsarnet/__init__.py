"""Hypothesis-neutral pulsar modulation detection and real-data ingestion."""

__version__ = "1.0.0"

from .models import PulseTrain, DetectionReport
from .simulator import simulate_natural_pulsar
from .encoding import inject_repeated_frame, build_frame
from .detector import scan_pulse_train, cross_node_correlation, benjamini_hochberg
from .observations import DynamicSpectrum, extract_pulse_train
from .framing import recover_repeated_frame
from .experiment import run_manifest
from .sensitivity import run_sensitivity

__all__ = [
    "PulseTrain", "DetectionReport", "DynamicSpectrum", "simulate_natural_pulsar",
    "inject_repeated_frame", "build_frame", "scan_pulse_train",
    "cross_node_correlation", "benjamini_hochberg", "extract_pulse_train", "recover_repeated_frame",
    "run_manifest", "run_sensitivity",
]
