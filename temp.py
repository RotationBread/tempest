import requests
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO

# =========================
# CONFIG
# =========================
API_KEY = "4ca9b677-d072-439f-8920-22ea9c630dd8"
DEVICE_ID = "470036"

START_DATE = datetime(2025, 12, 25, tzinfo=timezone.utc)
END_DATE = datetime.now(timezone.utc)

# Adjust if needed after checking header
FIELD_TIME = "timestamp"
FIELD_TEMP = "temperature"
FIELD_SOLAR = "solar_radiation"


def fetch_csv(start_ts, end_ts):
    url = (
        f"https://swd.weatherflow.com/swd/rest/observations/device/{DEVICE_ID}"
        f"?time_start={int(start_ts)}&time_end={int(end_ts)}"
        f"&format=csv&api_key={API_KEY}"
    )

    r = requests.get(url)
    r.raise_for_status()
    return r.text


def process_day(day_start):
    day_end = day_start + timedelta(days=1)

    csv_text = fetch_csv(day_start.timestamp(), day_end.timestamp())

    reader = csv.DictReader(StringIO(csv_text))

    


    max_temp = None
    max_row = None

    for row in reader:
        try:
            temp = float(row[FIELD_TEMP])
        except (ValueError, TypeError):
            continue

        if (max_temp is None) or (temp > max_temp):
            max_temp = temp
            max_row = row

    if not max_row:
        return None

    ts = datetime.fromtimestamp(int(max_row[FIELD_TIME]), tz=timezone.utc)

    try:
        solar = float(max_row[FIELD_SOLAR])
    except:
        solar = None

    return {
        "date": day_start.date(),
        "time": ts,
        "temp": max_temp,
        "solar": solar
    }


# =========================
# MAIN LOOP
# =========================
current = START_DATE
results = []

while current < END_DATE:
    try:
        result = process_day(current)
        if result:
            results.append(result)
    except Exception as e:
        print(f"Error on {current.date()}: {e}")

    current += timedelta(days=1)



# =========================
# OUTPUT
# =========================
for r in results:
    print(
        f"{r['date']} | "
        f"{r['time'].strftime('%H:%M:%S')} UTC | "
        f"{r['temp']:.2f}°F | "
        f"{r['solar']} W/m²"
    )