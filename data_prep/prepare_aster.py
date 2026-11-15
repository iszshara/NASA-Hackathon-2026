from pathlib import Path
import numpy as np
import h5py
import xarray as xr

DATA_DIR = Path(__file__).parent.parent / "data"


def find_dataset(f, wanted):
    # Pfad für Emmissivität durchsuchen"
    hits = []
    f.visititems(lambda name, obj: hits.append(name)
                 if isinstance(obj, h5py.Dataset) and name.lower().endswith(wanted.lower()) else None)
    return hits[0] if hits else None


def load_emissivity(path):
    with h5py.File(path, "r") as f:
        key = find_dataset(f, "Emissivity/Mean")
        if key is None:
            print("Struktur der Datei:")
            f.visit(print)
            raise KeyError("'Emissivity/Mean' nicht gefunden, Struktur siehe oben")

        dset = f[key]
        em = dset[:].astype("float32")
        fill = dset.attrs.get("_FillValue", -9999)
        scale = float(np.ravel(dset.attrs.get("scale_factor", [0.001]))[0])
        fill = float(np.ravel([fill])[0])

        # Breitengrad-Richtung prüfen, falls vorhanden
        lat_key = find_dataset(f, "Latitude")
        north_up = True
        if lat_key is not None:
            lat_arr = np.asarray(f[lat_key][:])
            col = lat_arr[:, 0] if lat_arr.ndim == 2 else lat_arr
            north_up = col[0] > col[-1]

    em[em == fill] = np.nan
    em[em <= -9000] = np.nan
    em = em * scale

    # Bandachse (Laenge 5) nach vorne
    band_axis = [i for i, n in enumerate(em.shape) if n == 5][0]
    em = np.moveaxis(em, band_axis, 0)
    if not north_up:
        em = em[:, ::-1, :]

    nlat, nlon = em.shape[1:]
    lat = 90 - (np.arange(nlat) + 0.5) * 180 / nlat
    lon = -180 + (np.arange(nlon) + 0.5) * 360 / nlon
    return xr.DataArray(em, coords={"band": [10, 11, 12, 13, 14], "lat": lat, "lon": lon},
                        dims=("band", "lat", "lon"))


def prepare_aster():
    files = sorted(p for p in DATA_DIR.glob("ASTER_GED*.h5")
                   if p.suffix.lower() in (".h5", ".hdf5", ".he5", ".hdf"))
    if not files:
        raise FileNotFoundError(f"Keine AG5KMMOH-Dateien in {DATA_DIR}")
    print(f"ASTER: {len(files)} Dateien")

    em = xr.concat([load_emissivity(p) for p in files], dim="time").mean("time")
    em = em.where((em > 0.5) & (em <= 1.0))  # unplausible Werte raus

    index = em.sel(band=[10, 11, 12]).mean("band") / em.sel(band=[13, 14]).mean("band")

    # auf 0,5 Grad bringen
    nlat = index.sizes["lat"]
    if nlat % 360 == 0:
        f = nlat // 360
        index = index.coarsen(lat=f, lon=f, boundary="trim").mean()
    else:
        lat = 89.75 - 0.5 * np.arange(360)
        lon = -179.75 + 0.5 * np.arange(720)
        index = index.interp(lat=lat, lon=lon)

    index.name = "basalt_index"
    index.to_netcdf(DATA_DIR / "aster_2024.nc")


if __name__ == "__main__":
    prepare_aster()