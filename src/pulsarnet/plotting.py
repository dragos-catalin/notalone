from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from .models import PulseTrain
from .detector import robust_binary


def save_diagnostic_plot(train: PulseTrain, path: str, start: int = 0, count: int = 1800) -> None:
    end = min(train.n_pulses, start + count)
    idx = np.arange(start, end)
    bits = robust_binary(train.amplitude)[start:end]

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(idx, train.amplitude[start:end], linewidth=0.8, label="pulse amplitude")
    ax.step(idx, bits * max(0.1, np.quantile(train.amplitude[start:end], 0.85)), where="mid", linewidth=0.7, label="on/null classification")
    ax.set_title(f"{train.source_id}: single-pulse diagnostic")
    ax.set_xlabel("Pulse index")
    ax.set_ylabel("Relative amplitude")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
