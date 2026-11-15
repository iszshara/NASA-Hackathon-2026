from pathlib import Path
import xarray as xr
from load_modis import load_cmg, date_from_name
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).parent.parent / "data"
files = sorted(DATA_DIR.glob("MOD13C2*.hdf"))

monate = []
for p in files:
    da = load_cmg(p, "CMG 0.05 Deg Monthly NDVI", scale=0.0001, fill=-3000)
    da = da.expand_dims(time=[date_from_name(p)])  # add time axis
    monate.append(da)

ndvi_all = xr.concat(monate, dim="time")
ndvi_max = ndvi_all.max("time").coarsen(lat=10, lon=10, boundary="trim").mean()
ndvi_max.to_netcdf(DATA_DIR / "ndvi_max_2024.nc")

da = xr.open_dataarray("../data/ndvi_max_2024.nc")
print(da.shape)  # (360, 720) bei 0,5°
da.plot(); plt.show()