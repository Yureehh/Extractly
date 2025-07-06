import numpy as np
from typing import Dict, List


def majority_vote(probs, labels):
    """Return (winner, confidence) given an array [[p(type1)…], …]."""
    mean = probs.mean(axis=0)
    idx = np.argmax(mean)
    return labels[idx], float(mean[idx])


def temp_scale(raw_scores, T):
    """Temperature-scale a list/np.array of raw confidences."""
    import scipy.special as sp

    logits = np.log(np.clip(raw_scores, 1e-6, 1 - 1e-6))
    return sp.softmax(logits / T)


def score_confidence(
    meta: Dict[str, str | None], schema: List[Dict]
) -> Dict[str, float]:
    """
    Given the extracted `meta` dict and the field `schema`, return a per-field
    confidence in the range [0, 1].  This naive version assigns:
        • 0.9  if the field has a non-empty value
        • 0.2  otherwise
    You can replace this later with something smarter.
    """
    conf: Dict[str, float] = {}
    for f in schema:
        name = f["name"]
        val = meta.get(name)
        conf[name] = 0.9 if val not in (None, "", "None") else 0.2
    return conf
