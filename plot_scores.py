"""
plot_scores.py - World heatmap of the Moon analog score.

Input:   data/scores_moon.nc, data/analog_scores.csv   (from score_map.py)
Output:  moon_score_map.png

Run:  python score_map.py   (once)
      python plot_scores.py
"""

import csv

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap

from score import DATA_DIR

OUTPUT = DATA_DIR.parent / "moon_score_map.png"

OCEAN = "#d9e2ea"
CMAP = LinearSegmentedColormap.from_list(
    "moon", ["#f3eee4", "#f2c879", "#e07b39", "#a3302a", "#3d0d1f"])


def main():
    scores = xr.open_dataset(DATA_DIR / "scores_moon.nc")
    score = scores["score"]
    lat, lon = score["lat"].values, score["lon"].values
    extent = [lon.min() - 0.25, lon.max() + 0.25, lat.min() - 0.25, lat.max() + 0.25]

    with open(DATA_DIR / "analog_scores.csv", encoding="utf-8") as f:
        analogs = list(csv.DictReader(f))

    fig, ax = plt.subplots(figsize=(16, 8.4))
    ax.set_facecolor(OCEAN)
    img = ax.imshow(score.values, extent=extent, origin="upper", cmap=CMAP,
                    vmin=0, vmax=1, interpolation="nearest")

    # known analog sites (labels alternate right/left so close sites don't overlap)
    labeled = 0
    for a in analogs:
        x, y = float(a["lon"]), float(a["lat"])
        s = float(a["score_moon"]) if a["score_moon"] else 0.0
        ax.scatter(x, y, s=60, marker="o", facecolor="white" if s < 0.3 else "#2f9e8f",
                   edgecolor="black", linewidth=1.0, zorder=3)
        if s >= 0.3:
            right = labeled % 2 == 0
            ax.annotate(f"{a['name']} ({s:.2f})", (x, y),
                        xytext=(7, 5) if right else (-7, -12), ha="left" if right else "right",
                        textcoords="offset points", fontsize=8.5, zorder=4,
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
            labeled += 1

    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 85)          # Antarctica has almost no data (ice) -> cut off
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Moon analog score on Earth (0 = not Moon-like, 1 = very Moon-like)\n"
                 "MODIS NDVI, LST, albedo + GPM IMERG precipitation (2024), "
                 "compared with LRO/Diviner Moon reference values, 0.5° grid",
                 fontsize=12)
    cbar = fig.colorbar(img, ax=ax, fraction=0.025, pad=0.01, shrink=0.75)
    cbar.set_label("Moon analog score")

    ax.scatter([], [], s=60, facecolor="#2f9e8f", edgecolor="black", label="known analog, score ≥ 0.3")
    ax.scatter([], [], s=60, facecolor="white", edgecolor="black", label="known analog, score < 0.3")
    ax.legend(loc="lower left", fontsize=9, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=150)
    print(f"saved: {OUTPUT}")


if __name__ == "__main__":
    main()
