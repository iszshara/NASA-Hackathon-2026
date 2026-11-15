"""
places.py - Manage single places (e.g. known analog sites), score and rank them.

Workflow:
    places = places_from_csv("data/known_analogs.csv")   # name, lat, lon (+ optional features)
    fill_from_grid(places, features_ds)                   # look up missing values in features.nc
    score_all(places, "moon")
    ranking(places, "moon")
    save_results(places, "data/analog_scores.csv")

Feature columns in the CSV are optional. Every column whose name is a raw
feature (see RAW_FEATURES) is read; empty cells = unknown.
Both comma- and semicolon-separated files (e.g. German Excel) work.
"""

import csv
import math
from dataclasses import dataclass, field

import numpy as np

from score import TARGETS, local_score

# raw features as they appear in features.nc / features.csv
RAW_FEATURES = ["ndvi_max", "lst_diff", "lst_max", "lst_min", "albedo",
                "rain_mm_year", "basalt_index"]


@dataclass
class Place:
    """A place on Earth with its feature values (dict name -> number).

    Example:  Place("Test desert", 23.4, 12.1, {"ndvi_max": 0.04, "albedo": 0.1})
    """
    name: str
    lat: float
    lon: float
    values: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)          # extra columns, e.g. typ, country
    results: dict = field(default_factory=dict, repr=False)

    def evaluate(self, planet="moon", **options):
        """Computes the score for one planet and stores it in the place."""
        score, parts, coverage = local_score(self.values, planet, **options)
        self.results[planet] = {
            "score": float(score),
            "coverage": float(coverage),
            "parts": {name: float(value) for name, value in parts.items()},
        }
        return self.results[planet]["score"]

    def score(self, planet="moon"):
        """Stored score (NaN if not evaluated yet)."""
        return self.results.get(planet, {}).get("score", math.nan)


def _number(text):
    """'0,05' / '0.05' / '' -> 0.05 / 0.05 / None"""
    text = (text or "").strip().replace(",", ".")
    return float(text) if text else None


def places_from_csv(path):
    """Reads a CSV file and creates one Place per row."""
    places = []
    with open(path, newline="", encoding="utf-8-sig") as file:
        header = file.readline()
        file.seek(0)
        delimiter = ";" if header.count(";") > header.count(",") else ","
        reader = csv.DictReader(file, delimiter=delimiter)

        for line_no, row in enumerate(reader, start=2):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            try:
                values = {k: _number(v) for k, v in row.items()
                          if k in RAW_FEATURES and _number(v) is not None}
                info = {k: v for k, v in row.items()
                        if k not in RAW_FEATURES and k not in ("name", "lat", "lon")}
                places.append(Place(row["name"], _number(row["lat"]), _number(row["lon"]),
                                    values, info))
            except (KeyError, ValueError, TypeError) as error:
                print(f"Warning: line {line_no} skipped ({error!r})")
    return places


def fill_from_grid(places, ds):
    """Fills missing feature values from the nearest grid cell of an xarray Dataset."""
    for place in places:
        cell = ds.sel(lat=place.lat, lon=place.lon, method="nearest")
        for name in ds.data_vars:
            value = float(cell[name])
            if name not in place.values and not np.isnan(value):
                place.values[name] = value


def score_all(places, planet="moon", **options):
    for place in places:
        place.evaluate(planet, **options)


def ranking(places, planet="moon", top=None):
    """Places sorted by score (best first). Unscored places go to the end."""
    def key(place):
        s = place.score(planet)
        return -1.0 if math.isnan(s) else s
    ordered = sorted(places, key=key, reverse=True)
    return ordered[:top] if top else ordered


def save_results(places, path, planets=("moon",)):
    """Writes name, lat, lon, info columns and all scores to a CSV."""
    info_cols = sorted({k for p in places for k in p.info})
    columns = ["name", "lat", "lon"] + info_cols
    for p in planets:
        columns += [f"score_{p}", f"coverage_{p}"] + [f"{p}_{f}" for f in TARGETS[p]]
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for place in places:
            row = [place.name, place.lat, place.lon] + [place.info.get(k, "") for k in info_cols]
            for p in planets:
                res = place.results.get(p)
                if res is None:
                    row += [""] * (2 + len(TARGETS[p]))
                    continue
                row += [round(res["score"], 4), round(res["coverage"], 4)]
                row += ["" if math.isnan(res["parts"][f]) else round(res["parts"][f], 4)
                        for f in TARGETS[p]]
            writer.writerow(row)
