import csv

INPUT_FILE = "record.csv"
OUTPUT_FILE = "temperature_only.csv"

# possible names your temperature column might have
TEMP_KEYS = ["temperature", "temp", "air_temperature"]

def find_temp_key(header):
    for key in TEMP_KEYS:
        if key in header:
            return key
    return None

with open(INPUT_FILE, "r", newline="") as infile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames

    if not fieldnames:
        raise ValueError("CSV has no headers")

    temp_key = find_temp_key(fieldnames)

    if not temp_key:
        raise ValueError(f"No temperature column found. Available columns: {fieldnames}")

    with open(OUTPUT_FILE, "w", newline="") as outfile:
        writer = csv.writer(outfile)

        # write header
        writer.writerow(["timestamp", temp_key])

        for row in reader:
            writer.writerow([
                row.get("timestamp", ""),
                row.get(temp_key, "")
            ])

print(f"Done -> {OUTPUT_FILE}")