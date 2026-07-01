import csv
from collections import deque
from datetime import datetime

# -----------------------
# Config
# -----------------------
INPUT_FILE = "master.csv"
OUTPUT_FILE = "record.csv"

TEMP_WINDOWS = {
    "temp_delta_5min": 5,
    "temp_delta_15min": 15,
    "temp_delta_30min": 30,
    "temp_delta_1hr": 60,
    "temp_delta_3hr": 180,
    "temp_delta_6hr": 360,
    "temp_delta_12hr": 720,
    "temp_delta_24hr": 1440,
    "temp_delta_48hr": 2880,
}

PRECIP_WINDOWS = {
    "precip_1hr": 60,
    "precip_3hr": 180,
    "precip_6hr": 360,
    "precip_12hr": 720,
    "precip_24hr": 1440,
}

LIGHTNING_WINDOW = 1440

PRECIP_TRUE_WINDOW = 1440  # NEW

# -----------------------
# Helpers
# -----------------------
def safe_float(x):
    try:
        if x in (None, "", "null"):
            return 0.0
        return float(x)
    except:
        return 0.0

def fmt_eta(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

# -----------------------
# Load
# -----------------------
with open(INPUT_FILE, "r") as f:
    reader = list(csv.DictReader(f))

total = len(reader)

fields = list(reader[0].keys())
new_fields = (
    list(TEMP_WINDOWS.keys())
    + list(PRECIP_WINDOWS.keys())
    + ["lightning_1day", "precip_true", "precip_true_24hr"]  # NEW
)
fieldnames = fields + new_fields

# -----------------------
# Buffers
# -----------------------
timestamps = []
temps = []
precips = []
lightnings = []

precip_true_list = []  # NEW

start_time = datetime.now()

output = []

# -----------------------
# Rolling pointers
# -----------------------
temp_ptrs = {k: 0 for k in TEMP_WINDOWS}
precip_ptrs = {k: 0 for k in PRECIP_WINDOWS}
lightning_ptr = 0
precip_true_ptr = 0  # NEW

# -----------------------
# Main loop
# -----------------------
for i, row in enumerate(reader):

    ts = int(row["timestamp"])
    temp = safe_float(row.get("air_temperature"))
    precip = safe_float(row.get("precip"))
    lightning = safe_float(row.get("lightning_strike_count"))

    timestamps.append(ts)
    temps.append(temp)
    precips.append(precip)
    lightnings.append(lightning)

    # -----------------------
    # PRECIP TRUE (NEW)
    # -----------------------
    curr_precip_min = safe_float(row.get("precip_minutes_local_day"))
    prev_precip_min = safe_float(reader[i - 1]["precip_minutes_local_day"]) if i > 0 else None

    if i == 0:
        precip_true = False
    else:
        precip_true = curr_precip_min > prev_precip_min

    row["precip_true"] = precip_true
    precip_true_list.append(precip_true)

    # -----------------------
    # TEMP DELTAS
    # -----------------------
    for name, mins in TEMP_WINDOWS.items():
        cutoff = ts - mins * 60
        p = temp_ptrs[name]

        while p < len(timestamps) and timestamps[p] < cutoff:
            p += 1

        temp_ptrs[name] = p

        if p < len(temps):
            row[name] = temp - temps[p]
        else:
            row[name] = 0

    # -----------------------
    # PRECIP WINDOWS
    # -----------------------
    for name, mins in PRECIP_WINDOWS.items():
        cutoff = ts - mins * 60
        p = precip_ptrs[name]

        while p < len(timestamps) and timestamps[p] < cutoff:
            p += 1

        precip_ptrs[name] = p

        row[name] = sum(precips[p:])

    # -----------------------
    # LIGHTNING 1 DAY
    # -----------------------
    cutoff = ts - LIGHTNING_WINDOW * 60

    while lightning_ptr < len(timestamps) and timestamps[lightning_ptr] < cutoff:
        lightning_ptr += 1

    row["lightning_1day"] = sum(lightnings[lightning_ptr:])

    # -----------------------
    # PRECIP TRUE 24HR (NEW)
    # -----------------------
    cutoff = ts - PRECIP_TRUE_WINDOW * 60

    while precip_true_ptr < len(timestamps) and timestamps[precip_true_ptr] < cutoff:
        precip_true_ptr += 1

    row["precip_true_24hr"] = sum(precip_true_list[precip_true_ptr:])

    output.append(row)

    # -----------------------
    # Progress
    # -----------------------
    if i % 10 == 0 or i == total - 1:
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        eta = (total - i - 1) / rate if rate > 0 else 0
        percent = (i + 1) / total * 100

        print(f"{i+1}/{total} ({percent:.2f}%) ({fmt_eta(eta)})")

# -----------------------
# Write
# -----------------------
with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output)

print("Done ->", OUTPUT_FILE)