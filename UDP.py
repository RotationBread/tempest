import socket
import json
import csv
import argparse
from datetime import datetime

UDP_IP = "0.0.0.0"
UDP_PORT = 50222

LIGHTNING_FILE = "lightning_csv.csv"
WIND_FILE = "wind_csv.csv"

# ------------------ Conversions ------------------
def epoch_to_local(epoch):
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %I:%M:%S %p")

def km_to_miles(km):
    return km * 0.621371

def mps_to_mph(mps):
    return mps * 2.23694

# ------------------ CSV Init ------------------
def init_csv(log_lightning, log_wind):
    if log_lightning:
        try:
            with open(LIGHTNING_FILE, "x", newline="") as f:
                csv.writer(f).writerow(["Time", "Distance_miles", "Energy"])
        except FileExistsError:
            pass

    if log_wind:
        try:
            with open(WIND_FILE, "x", newline="") as f:
                csv.writer(f).writerow(["Time", "WindSpeed_mph", "WindDirection_deg"])
        except FileExistsError:
            pass

# ------------------ Main ------------------
def main():
    parser = argparse.ArgumentParser(description="Tempest UDP Logger")
    parser.add_argument("--lightning", action="store_true", help="Log lightning strikes")
    parser.add_argument("--wind", action="store_true", help="Log rapid wind")
    parser.add_argument("--raw", action="store_true", help="Print all raw packets (no logging)")

    args = parser.parse_args()

    # If --raw is enabled, disable logging entirely
    if args.raw:
        log_lightning = False
        log_wind = False
    else:
        log_lightning = args.lightning or not (args.lightning or args.wind)
        log_wind = args.wind or not (args.lightning or args.wind)

    init_csv(log_lightning, log_wind)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print(f"Listening... Lightning={log_lightning}, Wind={log_wind}, Raw={args.raw}")

    while True:
        data, _ = sock.recvfrom(2048)

        try:
            decoded = data.decode("utf-8")
            msg = json.loads(decoded)
        except:
            print("⚠️ Non-JSON packet:", data)
            continue

        # ------------------ RAW MODE ------------------
        if args.raw:
            print(msg)
            continue

        msg_type = msg.get("type")

        # ------------------ LIGHTNING ------------------
        if msg_type == "evt_strike" and log_lightning:
            evt = msg.get("evt", [])

            if len(evt) >= 2:
                epoch = evt[0]
                distance_km = evt[1]
                energy = evt[2] if len(evt) >= 3 else None

                time_str = epoch_to_local(epoch)
                distance_mi = km_to_miles(distance_km)

                print(f"⚡ {time_str} | {distance_mi:.2f} mi | Energy: {energy}")

                with open(LIGHTNING_FILE, "a", newline="") as f:
                    csv.writer(f).writerow([
                        time_str,
                        f"{distance_mi:.2f}",
                        energy or ""
                    ])

        # ------------------ WIND ------------------
        elif msg_type == "rapid_wind" and log_wind:
            ob = msg.get("ob", [])

            if len(ob) >= 3:
                epoch = ob[0]
                wind_speed_mps = ob[1]
                wind_dir = ob[2]

                time_str = epoch_to_local(epoch)
                wind_mph = mps_to_mph(wind_speed_mps)

                print(f"💨 {time_str} | {wind_mph:.2f} mph | Dir: {wind_dir}°")

                with open(WIND_FILE, "a", newline="") as f:
                    csv.writer(f).writerow([
                        time_str,
                        f"{wind_mph:.2f}",
                        wind_dir
                    ])

if __name__ == "__main__":
    main()