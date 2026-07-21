import pandas as pd

# Load CSV (force DATE to be string so leading zeros are preserved)
df = pd.read_csv("Normals.csv", dtype={"DATE": str})

# Clean DATE column (remove any accidental .0 and ensure length 6)
df["DATE"] = df["DATE"].astype(str).str.split(".").str[0].str.zfill(6)

# Columns to interpolate (everything except DATE)
cols = [c for c in df.columns if c != "DATE"]

output_rows = []

for i in range(len(df) - 1):
    row_start = df.iloc[i]
    row_end = df.iloc[i + 1]

    date_start = row_start["DATE"]  # MMDDHH

    # Extract parts
    MM = date_start[:2]
    DD = date_start[2:4]
    HH = int(date_start[4:6])

    for minute in range(60):
        frac = minute / 60.0

        new_row = {}

        # New DATE: MMDDHHMM
        new_row["DATE"] = f"{MM}{DD}{HH:02d}{minute:02d}"

        # Interpolate each value
        for col in cols:
            v1 = float(row_start[col])
            v2 = float(row_end[col])

            interp_val = v1 + (v2 - v1) * frac
            new_row[col] = round(interp_val, 1)

        output_rows.append(new_row)

# Add final row (last hour at minute 00)
last = df.iloc[-1]
date_last = last["DATE"]

MM = date_last[:2]
DD = date_last[2:4]
HH = int(date_last[4:6])

final_row = {"DATE": f"{MM}{DD}{HH:02d}00"}
for col in cols:
    final_row[col] = round(float(last[col]), 1)

output_rows.append(final_row)

# Save output
out_df = pd.DataFrame(output_rows)
out_df.to_csv("normal_minute.csv", index=False)

print("Done. Saved as normal_minute.csv")