import csv
from datetime import datetime

input_file = "Normals.csv"
output_file = "Normals_epoch.csv"

with open(input_file, newline="") as infile, open(output_file, "w", newline="") as outfile:
    reader = csv.DictReader(infile)
    
    fieldnames = reader.fieldnames  # keep same columns
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        ts = row["timestamp"].strip()

        try:
            dt = datetime.strptime("2026-" + ts, "%Y-%m-%d %H:%M:%S")
            row["timestamp"] = int(dt.timestamp())  # overwrite here
        except Exception as e:
            print("ERROR on:", ts, e)
            row["timestamp"] = ""

        writer.writerow(row)

print("DONE → check Normals_epoch.csv")