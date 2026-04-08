import ephem
import datetime
import time
import math

# ===== CONFIG =====
LAT = '42.02'
LON = '-76.21'
YEAR = 2026
THRESHOLD = 58.0
LOW_ALT_SWITCH = 20.0  # switch to seconds above this
# ==================

observer = ephem.Observer()
observer.lat = LAT
observer.lon = LON

sun = ephem.Sun()

start_time = datetime.datetime(YEAR, 1, 1, 0, 0, 0)
end_time = datetime.datetime(YEAR + 1, 1, 1, 0, 0, 0)

def get_alt(dt):
    observer.date = dt
    sun.compute(observer)
    return float(sun.alt) * (180 / math.pi)

current_time = start_time
total_seconds = int((end_time - start_time).total_seconds())
processed_seconds = 0

results = {}

current_day = None
day_max_alt = -90
day_max_time = None
day_ranges = []

in_range = False
range_start = None

start_clock = time.time()

while current_time < end_time:
    alt = get_alt(current_time)

    day_str = current_time.strftime("%Y-%m-%d")

    # New day rollover
    if current_day != day_str:
        if current_day is not None:
            if day_ranges:
                results[current_day] = ("ranges", day_ranges)
            else:
                results[current_day] = ("max", day_max_alt, day_max_time)

        current_day = day_str
        day_max_alt = -90
        day_max_time = None
        day_ranges = []
        in_range = False
        range_start = None

    # Track max altitude (second precision when active)
    if alt > day_max_alt:
        day_max_alt = alt
        day_max_time = current_time

    # Threshold logic
    if not in_range and alt >= THRESHOLD:
        in_range = True
        range_start = current_time

    elif in_range and alt < THRESHOLD:
        day_ranges.append((range_start, current_time))
        in_range = False
        range_start = None

    # Decide step size
    if alt < LOW_ALT_SWITCH:
        step = 60  # seconds
    else:
        step = 1   # seconds

    # Progress tracking
    processed_seconds += step
    elapsed = time.time() - start_clock
    rate = processed_seconds / elapsed if elapsed > 0 else 0
    remaining = (total_seconds - processed_seconds) / rate if rate > 0 else 0
    eta_time = datetime.datetime.now() + datetime.timedelta(seconds=remaining)

    print(
        f"\rProgress: {processed_seconds}/{total_seconds} | "
        f"Last: {current_time} | Alt: {alt:.5f}° | "
        f"ETA: {eta_time.strftime('%Y-%m-%d %H:%M:%S')}",
        end=""
    )

    current_time += datetime.timedelta(seconds=step)

# Final day save
if current_day is not None:
    if day_ranges:
        results[current_day] = ("ranges", day_ranges)
    else:
        results[current_day] = ("max", day_max_alt, day_max_time)

print("\n\n=== RESULTS ===\n")

for day in sorted(results.keys()):
    data = results[day]

    if data[0] == "ranges":
        print(day)
        for start, end in data[1]:
            duration = (end - start).total_seconds()
            print(f"  {start.time()} → {end.time()} ({duration:.0f}s)")
    else:
        _, alt, t = data
        print(f"{day}: MAX {alt:.5f}° at {t.time()}")