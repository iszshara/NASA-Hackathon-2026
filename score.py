"""
score.py - Analog score (0.0 to 1.0) for Moon-like places on Earth.

Idea:
  1. For each feature (vegetation, rain, albedo, ...) the Earth value is
     compared with the target planet  ->  sub-score between 0 and 1.
  2. All sub-scores are combined into one weighted local score.

All functions use numpy, so they work with single numbers as well as with
whole 2D grids (lat x lon) - e.g. the arrays in data/features.nc.

Missing data is passed as NaN. It is ignored when combining the scores, but
lowers the "coverage", which in turn lowers the final score.

Feature names match the columns produced by data_prep/build.py:
    ndvi_max, lst_diff, lst_max, lst_min, albedo, rain_mm_year, basalt_index
"""

import json
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# 1. Building blocks: how (Earth value, target) becomes a sub-score
# ---------------------------------------------------------------------------

def score_gaussian(value, target, tolerance):
    """Bell curve: 1.0 exactly at the target, falls off on both sides.

    At a distance of 1x tolerance the score is ~0.61, at 2x ~0.14, at 3x ~0.01.
    """
    value = np.asarray(value, dtype=float)
    return np.exp(-0.5 * ((value - target) / tolerance) ** 2)


def score_lower_is_better(value, good, bad):
    """1.0 if value <= good, 0.0 if value >= bad, linear in between."""
    value = np.asarray(value, dtype=float)
    return np.clip((bad - value) / (bad - good), 0.0, 1.0)


def score_higher_is_better(value, bad, good):
    """0.0 if value <= bad, 1.0 if value >= good, linear in between."""
    value = np.asarray(value, dtype=float)
    return np.clip((value - bad) / (good - bad), 0.0, 1.0)


# ---------------------------------------------------------------------------
# 2. Configuration: target values per planet
# ---------------------------------------------------------------------------
# Moon reference values come from data/moon_reference.json (Diviner/LRO).
#
# Many Moon values are far outside anything that exists on Earth
# (e.g. a day/night temperature difference of ~295 K). A bell curve around
# the Moon value would give ~0 everywhere. For those features the rule is
# therefore "the closer to the Moon, the better", scaled to what Earth can
# reach:  bad = Earth median (land),  good = ~99th percentile of Earth land
# cells in the Moon direction (from features.nc, 2024).

with open(DATA_DIR / "moon_reference.json", encoding="utf-8") as f:
    MOON_REF = json.load(f)

TARGETS = {
    "moon": {
        # max. NDVI of the year: Moon = 0 (no vegetation). < 0.1 = practically bare
        "ndvi_max":     {"type": "lower", "good": 0.05, "bad": 0.3, "weight": 2.0},
        # precipitation in mm/year: Moon = 0. Earth land median ~380
        "rain_mm_year": {"type": "lower", "good": 25.0, "bad": 400.0, "weight": 2.0},
        # shortwave albedo: Moon maria ~0.07 -> the darker the better, snow/ice (~0.8) = 0.
        # (A bell curve around 0.07 was too strict: bright desert sand got ~0.)
        "albedo":       {"type": "lower", "good": max(MOON_REF["albedo"], 0.10),
                         "bad": 0.45, "weight": 1.5},
        # mean day/night LST difference in K: Moon ~295. Earth median ~5, p99 ~20
        "lst_diff":     {"type": "higher", "bad": 5.0, "good": 20.0, "weight": 1.0},
        # annual span lst_max - lst_min in K (derived): Moon ~295. Earth median ~33, p99 ~64
        "lst_span":     {"type": "higher", "bad": 33.0, "good": 60.0, "weight": 1.0},
        # ASTER basalt index - enable as soon as aster_2024.nc is part of features.nc.
        # Direction and thresholds still need to be checked with the data team.
        # "basalt_index": {"type": "higher", "bad": ..., "good": ..., "weight": 1.5},
    },
}


def add_derived(values):
    """Adds features that are computed from other features."""
    values = dict(values)
    if "lst_max" in values and "lst_min" in values:
        values["lst_span"] = np.asarray(values["lst_max"], float) - np.asarray(values["lst_min"], float)
    return values


# ---------------------------------------------------------------------------
# 3. Sub-score for one feature based on the configuration
# ---------------------------------------------------------------------------

def sub_score(value, rule):
    """Picks the matching building block based on rule['type'].

    Optional rule['minimum']: lower bound for the sub-score (for 'bonus
    features' whose absence should not push the score to 0).
    """
    kind = rule["type"]
    if kind == "gaussian":
        s = score_gaussian(value, rule["target"], rule["tolerance"])
    elif kind == "lower":
        s = score_lower_is_better(value, rule["good"], rule["bad"])
    elif kind == "higher":
        s = score_higher_is_better(value, rule["bad"], rule["good"])
    else:
        raise ValueError(f"Unknown rule type: {kind}")
    # np.fmax instead of np.maximum, so that NaN (missing data) stays NaN
    return np.where(np.isnan(s), np.nan, np.fmax(s, rule.get("minimum", 0.0)))


# ---------------------------------------------------------------------------
# 4. Combining sub-scores into the local score
# ---------------------------------------------------------------------------

def combine_scores(sub_scores, weights, method="geometric", coverage_penalty=1.0):
    """Combines sub-scores (dict name -> value/array) with weights.

    Returns: (score, coverage)
      coverage = share of the weights for which data is available (0..1).
      The score is multiplied by coverage ** coverage_penalty.
      coverage_penalty=0 disables the penalty, 1 = linear, 2 = strict.

    method="geometric" (recommended): if ONE important feature is ~0, the
        whole score goes towards 0 ('an analog has to match in everything').
    method="arithmetic": ordinary weighted mean.
    """
    names = list(sub_scores)
    arrays = np.broadcast_arrays(*[np.asarray(sub_scores[n], dtype=float) for n in names])
    s = np.stack(arrays)
    w = np.array([weights[n] for n in names], dtype=float)
    w = w.reshape((-1,) + (1,) * (s.ndim - 1))

    available = ~np.isnan(s)
    w_eff = np.where(available, w, 0.0)              # missing data -> weight 0
    w_sum = w_eff.sum(axis=0)
    coverage = w_sum / w.sum()

    with np.errstate(invalid="ignore", divide="ignore"):
        if method == "arithmetic":
            result = np.nansum(w_eff * s, axis=0) / w_sum
        elif method == "geometric":
            log_s = np.log(np.maximum(np.nan_to_num(s, nan=1.0), 1e-6))
            result = np.exp((w_eff * log_s).sum(axis=0) / w_sum)
        else:
            raise ValueError(f"Unknown method: {method}")

    result = result * coverage ** coverage_penalty
    result = np.where(w_sum > 0, result, np.nan)     # no data at all -> NaN
    return result, coverage


def local_score(earth_values, planet="moon", method="geometric",
                coverage_penalty=1.0, min_coverage=0.0):
    """Main function: Earth values (dict) -> (local score, sub-scores, coverage).

    min_coverage: cells with less coverage get NaN instead of a score
    (e.g. 0.5 removes ocean cells that only have rain data).
    """
    values = add_derived(earth_values)
    rules = TARGETS[planet]
    parts = {name: sub_score(values.get(name, np.nan), rule) for name, rule in rules.items()}
    weights = {name: rule["weight"] for name, rule in rules.items()}
    score, coverage = combine_scores(parts, weights, method, coverage_penalty)
    score = np.where(coverage >= min_coverage, score, np.nan)
    return score, parts, coverage


def score_dataset(ds, planet="moon", **options):
    """Scores a whole xarray Dataset (e.g. features.nc).

    Returns a new Dataset with 'score', 'coverage' and one 'part_<feature>'
    variable per sub-score, on the same lat/lon grid.
    """
    import xarray as xr
    values = {name: ds[name].values for name in ds.data_vars}
    score, parts, coverage = local_score(values, planet, **options)
    dims, coords = ds[list(ds.data_vars)[0]].dims, ds.coords
    out = xr.Dataset({"score": (dims, score), "coverage": (dims, coverage)}, coords=coords)
    for name, part in parts.items():
        out[f"part_{name}"] = (dims, np.broadcast_to(part, score.shape))
    out.attrs["planet"] = planet
    return out
