import requests # type: ignore
import csv
import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import math

# -----------------------
# Helpers
# -----------------------

def safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, str) and v.lower() in ["", "null", "none"]:
            return default
        return float(v)
    except:
        return default

def safe_int(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, str) and v.lower() in ["", "null", "none"]:
            return default
        return int(float(v))  # handles "3.0" too
    except:
        return default

def r(value, decimals):
    return round(value, decimals) if value is not None else None

def ms_to_mph(ms):
    return ms * 2.23694 if ms is not None else None

def c_to_f(c):
    return (c * 9 / 5) + 32 if c is not None else None

def mm_to_inches(mm):
    return mm / 25.4 if mm is not None else None

def wet_bulb_temp(T_c, RH, P_stn_mb):
    if T_c is None or RH is None or P_stn_mb is None:
        return None
    P_v = (RH / 100.0) * 6.112 * math.exp((17.67 * T_c) / (T_c + 243.5))
    Twb = T_c
    for _ in range(100):
        P_v_wb = 6.112 * math.exp((17.67 * Twb) / (Twb + 243.5))
        rhs = P_v_wb - P_stn_mb * (T_c - Twb) * 0.00066 * (1 + (0.00115 * Twb))
        diff = P_v - rhs
        if abs(diff) < 0.01:
            break
        Twb += diff * 0.1
    return Twb

# -----------------------
# Constants
# -----------------------
P0 = 1013.25
Rd = 287.05
gamma_s = 0.0065
g = 9.80665
T0 = 288.10
R_specific = 287.058

h_total = 460.21 + 1.37

DEVICE_ID = 470036
API_KEY = "4ca9b677-d072-439f-8920-22ea9c630dd8"

tz = ZoneInfo("America/New_York")

# -----------------------
# Time range
# -----------------------
start_dt = datetime(2025, 12, 25, 11, 0, tzinfo=tz)
end_dt = datetime.now(tz)

# -----------------------
# Build master minute timeline
# -----------------------
all_minutes = {}
current_dt = start_dt
while current_dt <= end_dt:
    all_minutes[int(current_dt.timestamp())] = None
    current_dt += timedelta(minutes=1)

total_minutes = len(all_minutes)

# -----------------------
# Build calendar days
# -----------------------
days = []
d = datetime(start_dt.year, start_dt.month, start_dt.day, tzinfo=tz)
end_day = datetime(end_dt.year, end_dt.month, end_dt.day, tzinfo=tz)

while d <= end_day:
    days.append(d)
    d += timedelta(days=1)

total_days = len(days)

# -----------------------
# Fetch per day
# -----------------------
minutes_logged = 0
days_fetched = 0

for day in days:
    seg_start = max(day, start_dt)
    seg_end = min(day + timedelta(days=1), end_dt)

    if seg_start >= seg_end:
        continue

    START = safe_int(seg_start.astimezone(timezone.utc).timestamp())
    END = safe_int(seg_end.astimezone(timezone.utc).timestamp())

    URL = (
        f"https://swd.weatherflow.com/swd/rest/observations/device/{DEVICE_ID}"
        f"?time_start={START}&time_end={END}&format=csv"
        f"&api_key={API_KEY}"
    )

    response = requests.get(URL)
    response.raise_for_status()

    rows = list(csv.DictReader(io.StringIO(response.text)))

    for row in rows:
        row["timestamp"] = safe_int(row["timestamp"])  # <-- add this
        ts = safe_int(row["timestamp"])
        if ts in all_minutes:
            if all_minutes[ts] is None:
                minutes_logged += 1
            all_minutes[ts] = row

    days_fetched += 1
    print(f"{minutes_logged}/{total_minutes} | {days_fetched}/{total_days}")

# -----------------------
# Fill missing minutes
# -----------------------
prev_row = None
filled_minutes = []

for ts in sorted(all_minutes.keys()):
    obs = all_minutes[ts]

    if obs is None:
        obs = prev_row.copy() if prev_row else {}
        obs["timestamp"] = ts
        for key in ["temperature","pressure","wind_avg","wind_dir","wind_gust","wind_lull",
                    "humidity","solar_radiation","uv","lux","precip","strike_count"]:
            obs[key] = prev_row[key] if prev_row and key in prev_row else 0
    else:
        for key in ["temperature","pressure","wind_avg","wind_dir","wind_gust","wind_lull",
                    "humidity","solar_radiation","uv","lux","precip","strike_count"]:
            if obs.get(key) in [None, ""]:
                obs[key] = prev_row[key] if prev_row and key in prev_row else 0

    prev_row = obs
    filled_minutes.append(obs)

# -----------------------
# CSV Output (FULL VERSION RESTORED)
# -----------------------
with open("master.csv", "w", newline="") as f:
    writer = csv.writer(f)

    writer.writerow([
        "timestamp","air_temperature","barometric_pressure","station_pressure","pressure_trend",
        "sea_level_pressure","relative_humidity","precip",
        "precip_accum_local_day","precip_accum_local_day_final",
        "precip_accum_local_yesterday_final","precip_minutes_local_day",
        "precip_minutes_local_yesterday_final","wind_avg","wind_direction",
        "wind_gust","wind_lull","solar_radiation","uv","brightness",
        "lightning_strike_count","lightning_strike_count_last_1hr",
        "lightning_strike_count_last_3hr","feels_like","heat_index",
        "wind_chill","dew_point","wet_bulb_temperature",
        "wet_bulb_globe_temperature","delta_t","air_density"
    ])

    current_day = None
    precip_minutes_today = 0
    precip_accum_today = 0.0
    precip_minutes_yesterday_final = 0
    precip_accum_yesterday_final = 0.0

    pressure_history = []
    lightning_1hr_sum = 0
    lightning_3hr_sum = 0
    idx_1hr = 0
    idx_3hr = 0

    for i, obs in enumerate(filled_minutes):
        timestamp_epoch = safe_int(obs["timestamp"])
        obs_date = datetime.fromtimestamp(safe_int(timestamp_epoch), tz=tz).date()

        if current_day is None:
            current_day = obs_date
        elif obs_date != current_day:
            precip_minutes_yesterday_final = precip_minutes_today
            precip_accum_yesterday_final = precip_accum_today
            precip_minutes_today = 0
            precip_accum_today = 0.0
            current_day = obs_date

        temperature_c = safe_float(obs["temperature"])
        temperature_f = c_to_f(temperature_c)
        humidity = safe_float(obs["humidity"])
        station_pressure_mb = safe_float(obs["pressure"])
        wind_avg_mph = ms_to_mph(safe_float(obs["wind_avg"]))
        wind_dir = safe_int(obs["wind_dir"])
        precip_in = mm_to_inches(safe_float(obs["precip"]))
        solar_rad = obs["solar_radiation"]
        uv = safe_float(obs["uv"])
        lux = safe_int(obs["lux"])
        strike_count = safe_int(obs["strike_count"])

        pressure_history.append((timestamp_epoch, station_pressure_mb))
        pressure_trend = None
        for ts_p, p in reversed(pressure_history):
            if ts_p <= timestamp_epoch - 10800:
                diff = station_pressure_mb - p
                if diff > 1:
                    pressure_trend = "Rising"
                elif diff < -1:
                    pressure_trend = "Dropping"
                else:
                    pressure_trend = "Steady"
                break

        sea_level_pressure_mb = station_pressure_mb * (
            1 + (P0 / station_pressure_mb) ** ((Rd * gamma_s) / g)
            * (gamma_s * h_total / T0)
        ) ** (g / (Rd * gamma_s))

        if precip_in > 0:
            precip_minutes_today += 1
            precip_accum_today += precip_in

        lightning_1hr_sum += strike_count
        lightning_3hr_sum += strike_count

        while idx_1hr < len(filled_minutes) and filled_minutes[idx_1hr]["timestamp"] < timestamp_epoch - 3600:
            lightning_1hr_sum -= safe_int(filled_minutes[idx_1hr]["strike_count"])
            idx_1hr += 1

        while idx_3hr < len(filled_minutes) and filled_minutes[idx_3hr]["timestamp"] < timestamp_epoch - 10800:
            lightning_3hr_sum -= safe_int(filled_minutes[idx_3hr]["strike_count"])
            idx_3hr += 1

        if temperature_f < 50 and wind_avg_mph > 3:
            wind_chill_f = 35.74 + 0.6215 * temperature_f - 35.75 * wind_avg_mph ** 0.16 + 0.4275 * temperature_f * wind_avg_mph ** 0.16
        else:
            wind_chill_f = temperature_f

        if temperature_f >= 80 and humidity >= 40:
            heat_index_f = -42.379 + 2.04901523 * temperature_f + 10.1433127 * humidity - 0.22475541 * temperature_f * humidity - 6.83783e-3 * temperature_f ** 2 - 5.481717e-2 * humidity ** 2 + 1.22874e-3 * temperature_f ** 2 * humidity + 8.5282e-4 * temperature_f * humidity ** 2 - 1.99e-6 * temperature_f ** 2 * humidity ** 2
        else:
            heat_index_f = temperature_f

        if solar_rad == "null":
            solar_rad = float((lux / 125) * 0.7 + (uv * 25))
        else:
            solar_rad = float(solar_rad)
        

        feels_like_f = wind_chill_f if temperature_f < 50 else heat_index_f if temperature_f >= 80 else temperature_f

        alpha = math.log(humidity / 100) + (17.625 * temperature_c) / (243.04 + temperature_c)
        dew_point_f = c_to_f(243.04 * alpha / (17.625 - alpha))

        wet_bulb_c = wet_bulb_temp(temperature_c, humidity, station_pressure_mb)
        wet_bulb_f = c_to_f(wet_bulb_c)

        WBGT_c = (0.7 * wet_bulb_c + 0.3 * temperature_c) if solar_rad <= 0 else (
            0.7 * wet_bulb_c +
            0.2 * (1.184 * temperature_c - 0.0789 * humidity + 0.01498 * solar_rad - 2.739) +
            0.1 * temperature_c
        )

        delta_t_f = temperature_f - wet_bulb_f
        air_density = (station_pressure_mb * 100) / (R_specific * (temperature_c + 273.15))

        writer.writerow([
            timestamp_epoch,
            r(temperature_f, 3),
            r(station_pressure_mb, 2),
            r(station_pressure_mb, 2),
            pressure_trend,
            r(sea_level_pressure_mb, 2),
            r(humidity, 2),
            r(precip_in, 6),
            r(precip_accum_today, 4),
            r(precip_accum_today, 4),
            r(precip_accum_yesterday_final, 4),
            precip_minutes_today,
            precip_minutes_yesterday_final,
            r(wind_avg_mph, 3),
            wind_dir,
            r(ms_to_mph(safe_float(obs["wind_gust"])), 3),
            r(ms_to_mph(safe_float(obs["wind_lull"])), 3),
            r(solar_rad, 1),
            r(uv, 3),
            lux,
            strike_count,
            lightning_1hr_sum,
            lightning_3hr_sum,
            r(feels_like_f, 3),
            r(heat_index_f, 3),
            r(wind_chill_f, 3),
            r(dew_point_f, 3),
            r(wet_bulb_f, 3),



            r(c_to_f(WBGT_c), 3),
            r(delta_t_f, 3),
            r(air_density, 5)
        ])

print("Master CSV saved to master.csv")