import csv
import concurrent.futures
import datetime
import io
import os
import re
import threading
import time
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None

BASE_URL = "https://www.spc.noaa.gov/products/outlook/archive"
START_DATE = datetime.date(2003, 1, 26)
END_DATE = datetime.date(2004, 5, 19)
RUNS = ["0730", "0830", "1100", "1200"]
OUTPUT_CSV = "spc_outlook_point_matches.csv"
TARGET_LAT = 42.024
TARGET_LON = -76.213
MAX_WORKERS = 64
THREAD_LOCAL = threading.local()
SESSION_LOCK = threading.Lock()


def get_requests_session():
    session = getattr(THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.25, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=["HEAD", "GET"])
        adapter = HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS, max_retries=retries)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        THREAD_LOCAL.session = session
    return session


def url_exists(url):
    if requests:
        session = get_requests_session()
        try:
            response = session.head(url, allow_redirects=True, timeout=20)
            return response.status_code < 400
        except requests.RequestException:
            try:
                response = session.get(url, stream=True, timeout=20)
                return response.status_code < 400
            except requests.RequestException:
                return False

    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=20):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        if exc.code == 405:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
                with urllib.request.urlopen(request, timeout=20):
                    return True
            except urllib.error.HTTPError as exc2:
                return exc2.code != 404
            except Exception:
                return True
        return False
    except Exception:
        return False


def download_kmz(url):
    if requests:
        session = get_requests_session()
        try:
            response = session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            raise

    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def extract_kml_from_kmz(kmz_bytes):
    with zipfile.ZipFile(io.BytesIO(kmz_bytes)) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".kml"):
                return zf.read(name).decode("utf-8", errors="replace")
    raise ValueError("No .kml file found inside KMZ archive")


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        if ((y0 > y) != (y1 > y)):
            x_int = x0 + (x1 - x0) * (y - y0) / (y1 - y0)
            if x < x_int:
                inside = not inside
    return inside


def parse_coordinates(text):
    coords = []
    for part in text.strip().split():
        if not part:
            continue
        fields = part.split(",")
        if len(fields) < 2:
            continue
        lon = float(fields[0])
        lat = float(fields[1])
        coords.append((lon, lat))
    return coords


def find_namespace(element):
    if element.tag.startswith("{"):
        return element.tag[1:element.tag.index("}")]
    return ""


def get_placemarks(root):
    ns = find_namespace(root)
    nsmap = {"kml": ns} if ns else {}
    placemarks = root.findall(".//kml:Placemark", nsmap) if ns else root.findall(".//Placemark")
    results = []

    for placemark in placemarks:
        name_el = placemark.find("kml:name", nsmap) if ns else placemark.find("name")
        desc_el = placemark.find("kml:description", nsmap) if ns else placemark.find("description")
        name = name_el.text.strip() if name_el is not None and name_el.text else "(no name)"
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
        polygons_list = []

        polygon_elements = placemark.findall(".//kml:Polygon", nsmap) if ns else placemark.findall(".//Polygon")
        for poly_el in polygon_elements:
            coords_el = poly_el.find(".//kml:coordinates", nsmap) if ns else poly_el.find(".//coordinates")
            if coords_el is None or not coords_el.text:
                continue
            coords = parse_coordinates(coords_el.text)
            if coords:
                polygons_list.append(coords)

        if polygons_list:
            results.append({"name": name, "description": description, "polygons": polygons_list})

    return results


def extract_percentage_label(placemark):
    percent_pattern = re.compile(r"(\d{1,3}%|\d{1,3}\.\d+%|\d+\s?percent)", re.IGNORECASE)
    candidates = [placemark["name"], placemark["description"]]
    for text in candidates:
        if not text:
            continue
        matches = percent_pattern.findall(text)
        for match in matches:
            cleaned = match.strip()
            if cleaned:
                return cleaned
    return ""


def iter_dates(start, end):
    current = start
    while current <= end:
        yield current
        current += datetime.timedelta(days=1)


def format_seconds(seconds):
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def print_progress(completed, total, start_time, current_key):
    elapsed = time.time() - start_time
    avg = elapsed / completed if completed else 0
    remaining = avg * (total - completed)
    etatime = elapsed + remaining
    percentage = completed / total
    status = (
        f"[{completed}/{total} ({percentage})] {current_key} elapsed={format_seconds(elapsed)} eta:{format_seconds(etatime)} [{format_seconds(remaining)}]"
    )
    print(status.ljust(120), end="\r", flush=True)


def process_job(date_obj, run, target, rows, lock, counters, start_time):
    date_str = date_obj.strftime("%Y%m%d")
    year = date_obj.strftime("%Y")
    key = f"{date_str}_{run}"
    url = f"{BASE_URL}/{year}/day3otlk_{date_str}_{run}.kmz"
    percentage_labels = []

    if not url_exists(url):
        with lock:
            counters["completed"] += 1
            print_progress(counters["completed"], counters["total"], start_time, key)
        return

    try:
        kmz_data = download_kmz(url)
    except Exception:
        with lock:
            rows.append((date_obj.isoformat(), run, ""))
            counters["completed"] += 1
            print(f"\n{key}: file found, matched=none")
            print_progress(counters["completed"], counters["total"], start_time, key)
        return

    try:
        kml_text = extract_kml_from_kmz(kmz_data)
    except Exception:
        with lock:
            rows.append((date_obj.isoformat(), run, ""))
            counters["completed"] += 1
            print(f"\n{key}: file found, matched=none")
            print_progress(counters["completed"], counters["total"], start_time, key)
        return

    try:
        root = ET.fromstring(kml_text)
    except ET.ParseError:
        with lock:
            rows.append((date_obj.isoformat(), run, ""))
            counters["completed"] += 1
            print(f"\n{key}: file found, matched=none")
            print_progress(counters["completed"], counters["total"], start_time, key)
        return

    placemarks = get_placemarks(root)
    for placemark in placemarks:
        for polygon in placemark["polygons"]:
            if point_in_polygon(target, polygon):
                label = extract_percentage_label(placemark)
                if label:
                    percentage_labels.append(label)
                break

    label_text = "; ".join(percentage_labels) if percentage_labels else "none"
    with lock:
        rows.append((date_obj.isoformat(), run, "; ".join(percentage_labels) if percentage_labels else ""))
        counters["completed"] += 1
        print(f"\n{key}: file found, matched={label_text}")
        print_progress(counters["completed"], counters["total"], start_time, key)


def main():
    total_days = (END_DATE - START_DATE).days + 1
    total_jobs = total_days * len(RUNS)
    target = (TARGET_LON, TARGET_LAT)
    counters = {"completed": 0, "total": total_jobs}
    lock = threading.Lock()
    start_time = time.time()
    rows = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for date_obj in iter_dates(START_DATE, END_DATE):
            for run in RUNS:
                futures.append(
                    executor.submit(
                        process_job,
                        date_obj,
                        run,
                        target,
                        rows,
                        lock,
                        counters,
                        start_time,
                    )
                )
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception:
                pass

    rows.sort(key=lambda row: (row[0], row[1]))
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "run", "percentage_polygon"])
        writer.writerows(rows)

    print(" " * 120, end="\r")
    print(f"Done. Output written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
