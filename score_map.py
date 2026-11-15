"""
score_map.py - Computes the Moon analog score for the whole Earth grid.

Input:   data/features.nc          (from data_prep/build.py)
         data/known_analogs.csv    (for validation)
Output:  data/scores_moon.nc       (grid: score, coverage, part_* - for the heatmap)
         data/scores_moon.csv      (one row per land cell - easy for the frontend)
         data/analog_scores.csv    (score of every known analog site)

Run:  python score_map.py
"""

import numpy as np
import xarray as xr

from places import fill_from_grid, places_from_csv, ranking, save_results, score_all
from score import DATA_DIR, score_dataset

PLANET = "moon"
MIN_COVERAGE = 0.5   # cells with less data (e.g. ocean: rain only) get no score


def main():
    features = xr.open_dataset(DATA_DIR / "features.nc").load()
    scores = score_dataset(features, PLANET, min_coverage=MIN_COVERAGE)

    scores.to_netcdf(DATA_DIR / f"scores_{PLANET}.nc")
    table = scores.to_dataframe().reset_index().dropna(subset=["score"])
    table.round(4).to_csv(DATA_DIR / f"scores_{PLANET}.csv", index=False)

    land = scores["score"].values[~np.isnan(scores["score"].values)]
    print(f"{len(land)} cells scored  ->  scores_{PLANET}.nc / scores_{PLANET}.csv")
    print("Score distribution:", "  ".join(
        f"p{p}={np.percentile(land, p):.2f}" for p in (25, 50, 75, 90, 99)))

    # --- Validation: where do the known analog sites end up? ----------------
    analogs = places_from_csv(DATA_DIR / "known_analogs.csv")
    fill_from_grid(analogs, features)
    score_all(analogs, PLANET, min_coverage=MIN_COVERAGE)
    save_results(analogs, DATA_DIR / "analog_scores.csv", planets=(PLANET,))

    print(f"\nKnown analogs (percentile = share of land cells with a lower score):")
    for place in ranking(analogs, PLANET):
        s = place.score(PLANET)
        pct = "   -" if np.isnan(s) else f"{(land < s).mean() * 100:4.0f}"
        parts = place.results[PLANET]["parts"]
        detail = " ".join(f"{k}={v:.2f}" for k, v in parts.items() if not np.isnan(v))
        print(f"  {place.name:36s} score={s:4.2f}  pct={pct}  | {detail}")

    # --- Top cells -----------------------------------------------------------
    print("\nTop 10 cells:")
    for _, row in table.nlargest(10, "score").iterrows():
        print(f"  lat={row.lat:7.2f} lon={row.lon:8.2f}  score={row.score:.2f}")


if __name__ == "__main__":
    main()
