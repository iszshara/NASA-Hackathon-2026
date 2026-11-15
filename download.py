import earthaccess
from pathlib import Path

earthaccess.login()
results_vegetation = earthaccess.search_data(short_name="MOD13C2", version="061", temporal=("2024-01-01", "2024-12-31"))
results_temperature = earthaccess.search_data(short_name="MOD11C3", version="061", temporal=("2024-01-01", "2024-12-31"))
results_brightness = earthaccess.search_data(short_name="MCD43C3", version="061", temporal=("2024-01-01", "2024-12-31"))
results_rainfall = earthaccess.search_data(short_name="GPM_3IMERGM", version="07", temporal=("2024-01-01", "2024-12-31"))
results_rock = earthaccess.search_data(short_name="AG5KMMOH", version="041")[:12]
results_height = earthaccess.search_data(
    short_name="NASADEM_HGT", version="001",
    bounding_box=(-113.8, 43.2, -113.3, 43.6),  # Craters of the Moon
)

results_brightness = [r for r in results_brightness
                      if r["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"][8:10] == "15"]

print(len(results_vegetation), len(results_temperature), len(results_brightness),
      len(results_rainfall), len(results_rock), len(results_height))

DATA_DIR = Path(__file__).parent / "data"
earthaccess.download(
    results_vegetation + results_temperature + results_brightness
    + results_rainfall + results_rock + results_height,
    str(DATA_DIR),
)