from pathlib import Path
import xarray as xr

DATA_DIR = Path(__file__).parent.parent / "data"


def prepare_gpm():
    files = sorted(DATA_DIR.glob("3B-MO.MS.MRG.3IMERG*.HDF5"))
    
    months = []
    for p in files:
        ds = xr.open_dataset(p, engine="h5netcdf", group="Grid")
        pr = ds["precipitation"].isel(time=0)     # mm/h, Monatsmittel
        pr = pr.where(pr >= 0)                     # Fill-Values (-9999.9) raus
        months.append(pr.transpose("lat", "lon").load())
        ds.close()

    pr_mean = xr.concat(months, dim="time").mean("time")
    rain = pr_mean * 24 * 365                      # mm/h -> mm/Jahr
    rain = rain.coarsen(lat=5, lon=5, boundary="trim").mean()  # 0,1 -> 0,5 Grad
    rain = rain.sortby("lat", ascending=False)     # Nord -> Süd wie MODIS
    rain = rain.drop_vars([c for c in rain.coords if c not in ("lat", "lon")])
    rain.name = "rain_mm_year"
    rain.to_netcdf(DATA_DIR / "rain_2024.nc")


if __name__ == "__main__":
    prepare_gpm()