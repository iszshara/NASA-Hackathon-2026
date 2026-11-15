from pathlib import Path
from datetime import datetime
import numpy as np
import xarray as xr
from pyhdf.SD import SD, SDC

###################
# Vegetation
###################


LAT = 89.975 - 0.05 * np.arange(3600)
LON = -179.975 + 0.05 * np.arange(7200)

def load_cmg(path, layer, scale, fill):
    f = SD(str(path), SDC.READ)
    raw = f.select(layer)[:].astype("float32")
    f.end()  
    raw[raw == fill] = np.nan
    return xr.DataArray(raw * scale, coords={"lat": LAT, "lon": LON}, dims=("lat", "lon"))

def date_from_name(path):
    # "MOD13C2.A2024001.061...." → "2024001" → 2024-01-01
    return datetime.strptime(path.name.split(".")[1][1:], "%Y%j")

DATA_DIR = Path(__file__).parent.parent / "data"
files = sorted(DATA_DIR.glob("MOD13C2*.hdf"))

monate = []
for p in files:
    da = load_cmg(p, "CMG 0.05 Deg Monthly NDVI", scale=0.0001, fill=-3000)
    da = da.expand_dims(time=[date_from_name(p)])  # add time axis
    monate.append(da)

ndvi_all = xr.concat(monate, dim="time")
print(ndvi_all.shape)