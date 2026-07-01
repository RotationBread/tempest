import csv
from tqdm import tqdm

INPUT_FILE = "record.csv"
OUTPUT_FILE = "record_time_series.csv"


def parse_csv():
    with open(INPUT_FILE, "r") as f:
        reader = csv.DictReader(f)
        data = []
        for row in reader:
            row["timestamp"] = int(row["timestamp"])
            for k, v in row.items():
                if k != "timestamp":
                    try:
                        row[k] = float(v)
                    except:
                        pass
            data.append(row)
        return data


def update_max(store, key, value, ts):
    if value is None:
        return
    if key not in store or value > store[key][0]:
        store[key] = (value, ts)


def update_min(store, key, value, ts):
    if value is None:
        return
    if key not in store or value < store[key][0]:
        store[key] = (value, ts)


def main():
    data = parse_csv()
    data.sort(key=lambda x: x["timestamp"])

    # running stats
    max_store = {}
    min_store = {}

    results = []

    for row in tqdm(data, desc="Processing", unit="row"):
        ts = row["timestamp"]

        def get(field):
            v = row.get(field)
            return v if isinstance(v, (int, float)) else None

        # ---- core temp ----
        update_max(max_store, "air_temperature", get("air_temperature"), ts)
        update_min(min_store, "air_temperature", get("air_temperature"), ts)

        # ---- delta fields ----
        temp_deltas = [
            "temp_delta_5min",
            "temp_delta_15min",
            "temp_delta_30min",
            "temp_delta_1hr",
            "temp_delta_3hr",
            "temp_delta_6hr",
            "temp_delta_12hr",
            "temp_delta_24hr",
            "temp_delta_48hr",
        ]

        for f in temp_deltas:
            update_max(max_store, f, get(f), ts)
            update_min(min_store, f, get(f), ts)

        # ---- max fields ----
        max_fields = [
            "wind_avg",
            "wind_gust",
            "wind_lull",
            "solar_radiation",
            "uv",
            "brightness",
            "precip",
            "precip_1hr",
            "precip_3hr",
            "precip_6hr",
            "precip_12hr",
            "precip_24hr",
            "precip_true_24hr",
            "lightning_strike_count_last_1hr",
            "lightning_strike_count_last_3hr",
            "lightning_1day",
            "air_density",
        ]

        for f in max_fields:
            update_max(max_store, f, get(f), ts)

        # ---- min fields ----
        min_fields = ["relative_humidity", "air_density"]
        for f in min_fields:
            update_min(min_store, f, get(f), ts)

        # ---- both ----
        both_fields = [
            "station_pressure",
            "sea_level_pressure",
            "feels_like",
            "wet_bulb_temperature",
            "wet_bulb_globe_temperature",
            "dew_point",
            "delta_t",
        ]

        for f in both_fields:
            update_max(max_store, f, get(f), ts)
            update_min(min_store, f, get(f), ts)

        # build output row
        out = {"timestamp": ts}

        for k, (v, t) in max_store.items():
            out[f"{k}_max"] = v

        for k, (v, t) in min_store.items():
            out[f"{k}_min"] = v

        results.append(out)

    # write output
    fieldnames = sorted(results[-1].keys())

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Done -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()