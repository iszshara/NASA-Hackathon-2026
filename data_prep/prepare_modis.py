"""NDVI, LST und Albedo aus MODIS-CMG-Dateien (0,05 Grad) -> je eine .nc auf 0,5 Grad."""
from pathlib import Path
import xarray as xr
from loaders import load_cmg, date_from_name

DATA_DIR = Path(__file__).parent.parent / "data"
COARSEN = dict(lat=10, lon=10, boundary="trim")  # 0,05 Grad -> 0,5 Grad


def load_stack(pattern, layer, scale, fill):
    """Alle Dateien eines Produkts laden und entlang 'time' stapeln."""
    files = sorted(DATA_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Keine Dateien fuer {pattern} in {DATA_DIR}")
    months = [
        load_cmg(p, layer, scale=scale, fill=fill).expand_dims(time=[date_from_name(p)])
        for p in files
    ]
    print(f"{layer}: {len(files)} Dateien")
    return xr.concat(months, dim="time")


def prepare_ndvi():
    ndvi = load_stack("MOD13C2*.hdf", "CMG 0.05 Deg Monthly NDVI", 0.0001, -3000)
    ndvi_max = ndvi.max("time").coarsen(**COARSEN).mean()
    ndvi_max.name = "ndvi_max"  # max. NDVI im Jahr (niedrig = kahl = mondaehnlich)
    ndvi_max.to_netcdf(DATA_DIR / "ndvi_max_2024.nc")


def prepare_lst():
    day = load_stack("MOD11C3*.hdf", "LST_Day_CMG", 0.02, 0)
    night = load_stack("MOD11C3*.hdf", "LST_Night_CMG", 0.02, 0)

    ds = xr.Dataset({
        "lst_diff": (day - night).mean("time"),   # Tag/Nacht-Differenz in K
        "lst_max": day.max("time") - 273.15,      # heissester Monat, Grad C
        "lst_min": night.min("time") - 273.15,    # kaeltester Monat, Grad C
    })
    ds.coarsen(**COARSEN).mean().to_netcdf(DATA_DIR / "lst_2024.nc")


def prepare_albedo():
    # White-Sky-Albedo, kurzwellig: 0 = schwarz, 1 = weiss. Mond-Maria ~0,07
    albedo = load_stack("MCD43C3*.hdf", "Albedo_WSA_shortwave", 0.001, 32767)
    albedo = albedo.where((albedo >= 0) & (albedo <= 1))
    albedo_mean = albedo.mean("time").coarsen(**COARSEN).mean()
    albedo_mean.name = "albedo"
    albedo_mean.to_netcdf(DATA_DIR / "albedo_2024.nc")


if __name__ == "__main__":
    prepare_ndvi()
    prepare_lst()
    prepare_albedo()