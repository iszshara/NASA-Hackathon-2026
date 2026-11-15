from pathlib import Path
import math
import xarray as xr
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).parent.parent / "data"
ds = xr.open_dataset(DATA_DIR / "features.nc")

CMAPS = {
    "ndvi_max": "YlGn",
    "lst_diff": "inferno",
    "lst_max": "inferno",
    "lst_min": "Blues_r",
    "albedo": "gray",
    "rain_mm_year": "Blues",
    "basalt_index": "viridis",
}

vars_ = list(ds.data_vars)
ncols = 2
nrows = math.ceil(len(vars_) / ncols)
fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.5 * nrows))

for ax, var in zip(axes.flat, vars_):
    ds[var].plot(ax=ax, cmap=CMAPS.get(var, "viridis"), robust=True)
    ax.set_title(var)
    ax.set_xlabel(""); ax.set_ylabel("")

for ax in axes.flat[len(vars_):]:  # leere Felder ausblenden
    ax.axis("off")

plt.tight_layout()
plt.savefig(DATA_DIR / "features_overview.png", dpi=150)
plt.show()