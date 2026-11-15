# alle Zwischenergebnisse in ein 0,5 Grad Gitter (features.nc)
# fehlende Dateien überspringen um Teildaten zu testen

from pathlib import Path
import numpy as np
import xarray as xr

DATA_DIR = Path(__file__).parent.parent / "data"

# gemeinsames Zielgitter (Zellmittelpunkte, Nord -> Süd, West -> Ost)
LAT = np.round(89.75 - 0.5 * np.arange(360), 3)
LON = np.round(-179.75 + 0.5 * np.arange(720), 3)

INPUTS = ["ndvi_max_2024.nc", "lst_2024.nc", "albedo_2024.nc", "rain_2024.nc", "aster_2024.nc"]


def to_grid(ds):
    #Koordinaten runden und exakt aufs Zielgitter legen (verhindert Float-Mismatch)
    ds = ds.assign_coords(lat=np.round(ds.lat.values, 3), lon=np.round(ds.lon.values, 3))
    return ds.reindex(lat=LAT, lon=LON, method="nearest", tolerance=0.01)


def build_features():
    parts = []
    for name in INPUTS:
        p = DATA_DIR / name
        if not p.exists():
            print(f"fehlt, uebersprungen: {name}")
            continue
        ds = xr.open_dataset(p)
        # unbenannte DataArrays bekommen sinnvolle Namen
        ds = ds.rename({v: name.replace("_2024.nc", "") for v in ds.data_vars
                        if v.startswith("__xarray")})
        parts.append(to_grid(ds.load()))
        print(f"geladen: {name} -> {list(ds.data_vars)}")

    features = xr.merge(parts)
    features.attrs["description"] = "Rohwerte pro 0,5-Grad-Zelle fuer das Mond-Scoring"
    features.to_netcdf(DATA_DIR / "features.nc")

    # zusaetzlich als Tabelle (eine Zeile pro Landzelle)
    df = features.to_dataframe().reset_index().dropna(
        subset=[v for v in features.data_vars], how="all")
    df.to_csv(DATA_DIR / "features.csv", index=False)

    print(features)
    print(f"{len(df)} Zellen mit Daten -> features.nc / features.csv")


if __name__ == "__main__":
    build_features()