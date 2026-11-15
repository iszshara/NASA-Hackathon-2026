from pathlib import Path
import xarray as xr
from loaders import load_cmg, date_from_name
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).parent.parent / "data"

def prepare_ndvi():

    
    files = sorted(DATA_DIR.glob("MOD13C2*.hdf"))

    months = []
    for p in files:
        da = load_cmg(p, "CMG 0.05 Deg Monthly NDVI", scale=0.0001, fill=-3000)
        da = da.expand_dims(time=[date_from_name(p)])  # add time axis
        months.append(da)

    ndvi_all = xr.concat(months, dim="time")
    ndvi_max = ndvi_all.max("time").coarsen(lat=10, lon=10, boundary="trim").mean()
    ndvi_max.to_netcdf(DATA_DIR / "ndvi_max_2024.nc")


def prepare_lst():

    DATA_DIR = Path(__file__).parent.parent / "data"
    files = sorted(DATA_DIR.glob("MOD11C3*.hdf"))

    days, nights = [], []
    for p in files:
        t = [date_from_name(p)]
        days.append(load_cmg(p, "LST_Day_CMG", scale=0.02, fill=0).expand_dims(time=t))
        nights.append(load_cmg(p, "LST_Night_CMG", scale=0.02, fill=0).expand_dims(time=t))

    day = xr.concat(days, dim="time")
    night = xr.concat(nights, dim="time")

    lst_diff = (day - night).mean("time")
    lst_max = day.max("time") - 273.15
    lst_min = night.min("time") - 273.15

    ds = xr.Dataset({"lst_diff": lst_diff, "lst_max": lst_max, "lst_min": lst_min})
    ds = ds.coarsen(lat=10, lon=10, boundary="trim").mean()
    ds.to_netcdf(DATA_DIR / "lst_2024.nc")

def prepare_albedo():
    pass




if __name__ == "__main__":
    prepare_ndvi()
    prepare_lst()
    prepare_albedo()

    ds = xr.open_dataset(DATA_DIR / "lst_2024.nc")
    print(ds)
    for var in ["lst_diff", "lst_max", "lst_min"]:
        ds[var].plot(); plt.show()
