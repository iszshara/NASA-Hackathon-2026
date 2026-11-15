import earthaccess
from pathlib import Path

earthaccess.login()
results_vegetation = earthaccess.search_data(short_name="MOD13C2", version="061", temporal=("2024-01-01", "2024-12-31"))
results_temperature = earthaccess.search_data(short_name="MOD11C3", version="061", temporal=("2024-01-01", "2024-12-31"))

print(len(results_vegetation), len(results_temperature))

DATA_DIR = Path(__file__).parent / "data"
earthaccess.download(results_vegetation + results_temperature, str(DATA_DIR))