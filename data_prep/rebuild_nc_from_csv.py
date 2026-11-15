# features.nc aus features.csv wiederherstellen (falls features.nc fehlt oder leer ist)
# gleiches 0,5-Grad-Gitter wie in build.py

from pathlib import Path
import pandas as pd

from build import DATA_DIR, LAT, LON


def rebuild():
    df = pd.read_csv(DATA_DIR / "features.csv")
    df["lat"] = df["lat"].round(3)
    df["lon"] = df["lon"].round(3)
    features = df.set_index(["lat", "lon"]).to_xarray().reindex(lat=LAT, lon=LON)
    features.attrs["description"] = "Rohwerte pro 0,5-Grad-Zelle fuer das Mond-Scoring"
    features.to_netcdf(DATA_DIR / "features.nc")
    print(features)


if __name__ == "__main__":
    rebuild()
