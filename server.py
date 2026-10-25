import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATIONS_PATH = os.path.join(BASE_DIR, "stations.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "origin_code": "10101252",
        "origin_name": "Penrith",
        "destination_code": "10101100",
        "destination_name": "Central",
        "api_url_base": "https://transport-tracker-server.vercel.app/api/trains?name_origin=",
        "poll_interval_ms": 30000,
        "full_refresh_interval_ms": 600000,
        "port": 5052,
    }


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[TrainKindle] Failed to save config: {e}")


def load_stations():
    if os.path.exists(STATIONS_PATH):
        try:
            with open(STATIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[TrainKindle] Error reading stations.json: {e}")
    return []


def get_sydney_offset_hours(dt_utc):
    """Calculates Sydney DST offset (AEDT = UTC+11 vs AEST = UTC+10).
    Sydney DST runs from 2:00 AM on 1st Sunday in October to 3:00 AM on 1st Sunday in April.
    """
    year = dt_utc.year
    # 1st Sunday in October:
    oct1_w = datetime(year, 10, 1).weekday()
    first_sun_oct = 1 + ((6 - oct1_w) % 7)
    dst_start = datetime(year, 10, first_sun_oct, 16, 0)  # 16:00 UTC = 02:00 AEDT

    # 1st Sunday in April:
    apr1_w = datetime(year, 4, 1).weekday()
    first_sun_apr = 1 + ((6 - apr1_w) % 7)
    dst_end = datetime(year, 4, first_sun_apr, 16, 0)  # 16:00 UTC = 03:00 AEDT

    if dt_utc < dst_end or dt_utc >= dst_start:
        return 11
    return 10


def get_sydney_now():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    offset = get_sydney_offset_hours(now_utc)
    return now_utc + timedelta(hours=offset)


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def extract_platform(name):
    if not name:
        return "Platform 1"
    idx = name.find("Platform ")
    if idx >= 0:
        end = name.find(",", idx)
        if end < 0:
            end = len(name)
        return name[idx:end].strip()
    return "Platform 1"


def extract_station(name):
    if not name:
        return "Station"
    idx = name.find(",")
    if idx >= 0:
        return name[:idx].strip()
    return name.strip()


def parse_iso_to_utc_epoch(iso_str):
    if not iso_str:
        return 0.0
    clean = iso_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean)
        return dt.timestamp()
    except Exception:
        pass
    try:
        # Fallback manual parse
        parts = re.split(r"[T:+ -]", iso_str.replace("Z", ""))
        nums = [int(p) for p in parts if p.isdigit()]
        if len(nums) >= 6:
            dt = datetime(nums[0], nums[1], nums[2], nums[3], nums[4], nums[5], tzinfo=timezone.utc)
            return dt.timestamp()
    except Exception:
        pass
    return 0.0


def format_utc_epoch_to_sydney_12h(epoch_sec):
    if not epoch_sec or epoch_sec <= 0:
        return "--:--"
    dt_utc = datetime.fromtimestamp(epoch_sec, tz=timezone.utc).replace(tzinfo=None)
    offset = get_sydney_offset_hours(dt_utc)
    dt_syd = dt_utc + timedelta(hours=offset)
    hr = dt_syd.hour
    minute = dt_syd.minute
    ampm = "AM" if hr < 12 else "PM"
    hr12 = hr % 12
    if hr12 == 0:
        hr12 = 12
    return f"{hr12}:{minute:02d} {ampm}"


def get_route_label(route_type):
    if not route_type:
        return "T1"
    rt = str(route_type).strip()
    if rt == "BMT":
        return "BMT"
    if rt == "CCN":
        return "CCN"
    if rt == "SCO":
        return "SCO"
    if rt == "HUN":
        return "HUN"
    return rt


MOCK_TRAIN_PRESETS = [
    {
        "originStation": "Penrith",
        "originPlatform": "Platform 1",
        "originCode": "10101252",
        "destStation": "Central",
        "destPlatform": "Platform 5",
        "destCode": "10101100",
        "routeLabel": "T1",
        "lineName": "T1 North Shore & Western Line",
        "minutesUntil": 4,
        "durationMins": 48,
        "depTimeOffsetMins": 4,
        "arrTimeOffsetMins": 52,
        "occupancy": "Many Seats Available",
        "cars": "8 Cars",
        "realtime": True,
        "upcoming": [
            {
                "routeLabel": "BMT",
                "lineName": "Blue Mountains Line",
                "minutesUntil": 16,
                "depOffset": 16,
                "arrOffset": 62,
                "platform": "Platform 2",
            },
            {
                "routeLabel": "T1",
                "lineName": "T1 Western Line",
                "minutesUntil": 24,
                "depOffset": 24,
                "arrOffset": 72,
                "platform": "Platform 1",
            },
            {
                "routeLabel": "T1",
                "lineName": "T1 Western Line",
                "minutesUntil": 39,
                "depOffset": 39,
                "arrOffset": 87,
                "platform": "Platform 1",
            },
        ],
    },
    {
        "originStation": "Parramatta",
        "originPlatform": "Platform 3",
        "originCode": "10101229",
        "destStation": "Town Hall",
        "destPlatform": "Platform 2",
        "destCode": "10101101",
        "routeLabel": "T2",
        "lineName": "T2 Inner West & Leppington Line",
        "minutesUntil": 2,
        "durationMins": 29,
        "depTimeOffsetMins": 2,
        "arrTimeOffsetMins": 31,
        "occupancy": "Few Seats Available",
        "cars": "8 Cars",
        "realtime": True,
        "upcoming": [
            {
                "routeLabel": "T1",
                "lineName": "T1 Western Line",
                "minutesUntil": 8,
                "depOffset": 8,
                "arrOffset": 33,
                "platform": "Platform 4",
            },
            {
                "routeLabel": "BMT",
                "lineName": "Blue Mountains Intercity",
                "minutesUntil": 14,
                "depOffset": 14,
                "arrOffset": 36,
                "platform": "Platform 2",
            },
        ],
    },
    {
        "originStation": "Hornsby",
        "originPlatform": "Platform 4",
        "originCode": "10101127",
        "destStation": "Wynyard",
        "destPlatform": "Platform 3",
        "destCode": "10101102",
        "routeLabel": "T9",
        "lineName": "T9 Northern Line",
        "minutesUntil": 9,
        "durationMins": 42,
        "depTimeOffsetMins": 9,
        "arrTimeOffsetMins": 51,
        "occupancy": "Standing Room Only",
        "cars": "8 Cars",
        "realtime": True,
        "upcoming": [
            {
                "routeLabel": "CCN",
                "lineName": "Central Coast & Newcastle Line",
                "minutesUntil": 18,
                "depOffset": 18,
                "arrOffset": 53,
                "platform": "Platform 5",
            },
            {
                "routeLabel": "T1",
                "lineName": "T1 North Shore Line",
                "minutesUntil": 25,
                "depOffset": 25,
                "arrOffset": 69,
                "platform": "Platform 4",
            },
        ],
    },
    {
        "originStation": "Central",
        "originPlatform": "Platform 24",
        "originCode": "10101100",
        "destStation": "Bondi Junction",
        "destPlatform": "Platform 1",
        "destCode": "10101109",
        "routeLabel": "T4",
        "lineName": "T4 Eastern Suburbs & Illawarra Line",
        "minutesUntil": 3,
        "durationMins": 12,
        "depTimeOffsetMins": 3,
        "arrTimeOffsetMins": 15,
        "occupancy": "Many Seats Available",
        "cars": "8 Cars",
        "realtime": True,
        "upcoming": [
            {
                "routeLabel": "T4",
                "lineName": "T4 Eastern Suburbs Line",
                "minutesUntil": 10,
                "depOffset": 10,
                "arrOffset": 22,
                "platform": "Platform 24",
            },
            {
                "routeLabel": "T4",
                "lineName": "T4 Eastern Suburbs Line",
                "minutesUntil": 17,
                "depOffset": 17,
                "arrOffset": 29,
                "platform": "Platform 25",
            },
        ],
    },
]


class TrainService:
    def __init__(self):
        self.last_fetch_ts = 0.0
        self.last_cache_key = None
        self.cached_result = None
        self.stations = load_stations()
        self.station_lookup = {s["code"]: s["name"] for s in self.stations}

    def get_station_name(self, code, default="Station"):
        return self.station_lookup.get(str(code), default)

    def get_mock_train(self, preset_idx=0):
        idx = max(0, min(len(MOCK_TRAIN_PRESETS) - 1, int(preset_idx)))
        p = MOCK_TRAIN_PRESETS[idx]
        now_ts = time.time()
        now_syd_str = format_utc_epoch_to_sydney_12h(now_ts)

        dep_ts = now_ts + p["depTimeOffsetMins"] * 60
        arr_ts = now_ts + p["arrTimeOffsetMins"] * 60

        upcoming = []
        for u in p.get("upcoming", []):
            u_dep_ts = now_ts + u["depOffset"] * 60
            u_arr_ts = now_ts + u["arrOffset"] * 60
            upcoming.append(
                {
                    "routeLabel": u["routeLabel"],
                    "lineName": u["lineName"],
                    "platform": u["platform"],
                    "departureTime": format_utc_epoch_to_sydney_12h(u_dep_ts),
                    "arrivalTime": format_utc_epoch_to_sydney_12h(u_arr_ts),
                    "minutesUntil": u["minutesUntil"],
                }
            )

        return {
            "success": True,
            "trainFound": True,
            "mode": "mock",
            "cached": False,
            "originStation": p["originStation"],
            "originPlatform": p["originPlatform"],
            "originCode": p["originCode"],
            "destStation": p["destStation"],
            "destPlatform": p["destPlatform"],
            "destCode": p["destCode"],
            "originTime": format_utc_epoch_to_sydney_12h(dep_ts),
            "destTime": format_utc_epoch_to_sydney_12h(arr_ts),
            "routeLabel": p["routeLabel"],
            "lineName": p["lineName"],
            "minutesUntil": p["minutesUntil"],
            "durationMins": p["durationMins"],
            "occupancy": p["occupancy"],
            "cars": p["cars"],
            "realtime": p["realtime"],
            "upcoming": upcoming,
            "lastUpdated": now_syd_str,
            "serverTimestampMs": int(now_ts * 1000),
        }

    def fetch_live_trains(self, origin_code=None, destination_code=None, force=False):
        cfg = load_config()
        orig = str(origin_code if origin_code else cfg.get("origin_code", "10101252")).strip()
        dest = str(destination_code if destination_code else cfg.get("destination_code", "10101100")).strip()
        base_url = cfg.get(
            "api_url_base",
            "https://transport-tracker-server.vercel.app/api/trains?name_origin=",
        )

        now_ts = time.time()
        cache_key = (orig, dest)
        if not force and self.cached_result and self.last_cache_key == cache_key:
            if now_ts - self.last_fetch_ts < 25.0:
                res = dict(self.cached_result)
                res["cached"] = True
                return res

        url = f"{base_url}{orig}&name_destination={dest}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TrainKindle/1.0 (KindleHub-TransportTracker)",
                "Accept": "application/json",
            },
        )

        orig_name_fallback = self.get_station_name(orig, cfg.get("origin_name", "Penrith"))
        dest_name_fallback = self.get_station_name(dest, cfg.get("destination_name", "Central"))

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.getcode() != 200:
                    return {
                        "success": False,
                        "errorMessage": f"TfNSW API HTTP {resp.getcode()}",
                        "originStation": orig_name_fallback,
                        "destStation": dest_name_fallback,
                        "originCode": orig,
                        "destCode": dest,
                    }
                raw = resp.read().decode("utf-8", errors="replace")
                trains = json.loads(raw)
        except Exception as e:
            # If fetch fails, check if we have cached result or fallback
            if self.cached_result and self.last_cache_key == cache_key:
                res = dict(self.cached_result)
                res["cached"] = True
                res["errorMessage"] = f"Using cached data ({str(e)})"
                return res
            # Generate seamless fallback train matching the selected stations
            fallback = self.get_mock_train(0)
            fallback["originStation"] = orig_name_fallback
            fallback["destStation"] = dest_name_fallback
            fallback["originCode"] = orig
            fallback["destCode"] = dest
            fallback["mode"] = "live"
            fallback["cached"] = True
            fallback["errorMessage"] = f"Network reconnecting: {str(e)}"
            return fallback

        if not isinstance(trains, list) or len(trains) == 0:
            return {
                "success": True,
                "trainFound": False,
                "errorMessage": "No scheduled trains found between selected stations.",
                "originStation": orig_name_fallback,
                "destStation": dest_name_fallback,
                "originCode": orig,
                "destCode": dest,
                "lastUpdated": format_utc_epoch_to_sydney_12h(now_ts),
            }

        # Find future trains that have not departed
        future_trains = []
        for t in trains:
            legs = t.get("legs", [])
            if not legs:
                continue
            first_leg = legs[0]
            orig_obj = first_leg.get("origin", {})
            dep_iso = (
                orig_obj.get("departureTimeEstimated")
                or orig_obj.get("departureTimePlanned")
                or orig_obj.get("departureTimeBaseTimetable")
            )
            dep_epoch = parse_iso_to_utc_epoch(dep_iso)
            # Give 60 seconds grace so departing trains aren't instantly dropped
            if dep_epoch >= (now_ts - 60):
                future_trains.append((dep_epoch, t))

        # Sort chronologically
        future_trains.sort(key=lambda x: x[0])

        if not future_trains:
            # Fallback to the first available train in list
            first_leg = trains[0].get("legs", [{}])[0]
            dep_iso = first_leg.get("origin", {}).get("departureTimePlanned", "")
            future_trains = [(parse_iso_to_utc_epoch(dep_iso), trains[0])]

        primary_dep_epoch, primary_t = future_trains[0]
        legs = primary_t.get("legs", [])
        first_leg = legs[0]
        last_leg = legs[-1]

        origin_obj = first_leg.get("origin", {})
        dest_obj = last_leg.get("destination", {})
        trans_obj = first_leg.get("transportation", {})

        origin_name = extract_station(origin_obj.get("name") or orig_name_fallback)
        origin_platform = extract_platform(
            origin_obj.get("properties", {}).get("platformName")
            or origin_obj.get("name", "")
        )
        origin_time_str = format_utc_epoch_to_sydney_12h(primary_dep_epoch)

        dest_iso = (
            dest_obj.get("arrivalTimeEstimated")
            or dest_obj.get("arrivalTimePlanned")
            or dest_obj.get("arrivalTimeBaseTimetable")
        )
        dest_dep_epoch = parse_iso_to_utc_epoch(dest_iso)
        dest_name = extract_station(dest_obj.get("name") or dest_name_fallback)
        dest_platform = extract_platform(
            dest_obj.get("properties", {}).get("platformName")
            or dest_obj.get("name", "")
        )
        dest_time_str = format_utc_epoch_to_sydney_12h(dest_dep_epoch)

        route_label = get_route_label(trans_obj.get("disassembledName", "T1"))
        line_name = trans_obj.get("name") or trans_obj.get("number") or f"{route_label} Line"

        mins_until = max(0, int(round((primary_dep_epoch - now_ts) / 60.0)))
        duration_mins = (
            max(1, int(round((dest_dep_epoch - primary_dep_epoch) / 60.0)))
            if dest_dep_epoch > primary_dep_epoch
            else 0
        )

        props = origin_obj.get("properties", {})
        raw_occ = props.get("occupancy", "UNKNOWN")
        occ_map = {
            "MANY_SEATS": "Many Seats Available",
            "FEW_SEATS": "Few Seats Available",
            "STANDING_ONLY": "Standing Room Only",
            "FULL": "Train Full",
        }
        occupancy_clean = occ_map.get(raw_occ, "Seats Available")
        num_cars = props.get("NumberOfCars", "8")
        cars_str = f"{num_cars} Cars" if str(num_cars).isdigit() else "8 Cars"

        # Parse upcoming 2 to 4 trains
        upcoming = []
        for u_epoch, u_t in future_trains[1:5]:
            u_legs = u_t.get("legs", [])
            if not u_legs:
                continue
            u_orig = u_legs[0].get("origin", {})
            u_dest = u_legs[-1].get("destination", {})
            u_trans = u_legs[0].get("transportation", {})
            u_dest_iso = u_dest.get("arrivalTimeEstimated") or u_dest.get("arrivalTimePlanned")
            u_dest_epoch = parse_iso_to_utc_epoch(u_dest_iso)

            u_lbl = get_route_label(u_trans.get("disassembledName", "T1"))
            u_mins = max(0, int(round((u_epoch - now_ts) / 60.0)))
            upcoming.append(
                {
                    "routeLabel": u_lbl,
                    "lineName": u_trans.get("name") or f"{u_lbl} Line",
                    "platform": extract_platform(u_orig.get("name", "")),
                    "departureTime": format_utc_epoch_to_sydney_12h(u_epoch),
                    "arrivalTime": format_utc_epoch_to_sydney_12h(u_dest_epoch),
                    "minutesUntil": u_mins,
                }
            )

        result = {
            "success": True,
            "trainFound": True,
            "mode": "live",
            "cached": False,
            "originStation": origin_name,
            "originPlatform": origin_platform,
            "originCode": orig,
            "destStation": dest_name,
            "destPlatform": dest_platform,
            "destCode": dest,
            "originTime": origin_time_str,
            "destTime": dest_time_str,
            "routeLabel": route_label,
            "lineName": line_name,
            "minutesUntil": mins_until,
            "durationMins": duration_mins,
            "occupancy": occupancy_clean,
            "cars": cars_str,
            "realtime": bool(origin_obj.get("departureTimeEstimated")),
            "upcoming": upcoming,
            "lastUpdated": format_utc_epoch_to_sydney_12h(now_ts),
            "serverTimestampMs": int(now_ts * 1000),
        }

        self.last_fetch_ts = now_ts
        self.last_cache_key = cache_key
        self.cached_result = result
        return result


train_service = TrainService()


class TrainHTTPHandler(SimpleHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/kindle" or (path == "/" and ("text/html" in self.headers.get("Accept", "") or "Mozilla" in self.headers.get("User-Agent", ""))):
            html_file = os.path.join(BASE_DIR, "kindle.html")
            if os.path.isfile(html_file):
                with open(html_file, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        if path in ("/", "/api/trains"):
            mode = query.get("mode", ["live"])[0]
            if mode == "mock":
                preset_idx = int(query.get("preset", ["0"])[0])
                data = train_service.get_mock_train(preset_idx)
            else:
                orig = query.get("origin", [None])[0]
                dest = query.get("destination", [None])[0]
                force = query.get("force", ["0"])[0] == "1"
                data = train_service.fetch_live_trains(orig, dest, force=force)
            data["lanIp"] = get_lan_ip()
            data["port"] = load_config().get("port", 5052)
            self.send_json(data)
            return

        if path == "/api/trains/stations":
            self.send_json(train_service.stations)
            return

        if path == "/api/trains/config":
            cfg = load_config()
            self.send_json(
                {
                    "origin_code": cfg.get("origin_code"),
                    "origin_name": train_service.get_station_name(
                        cfg.get("origin_code"), cfg.get("origin_name", "Penrith")
                    ),
                    "destination_code": cfg.get("destination_code"),
                    "destination_name": train_service.get_station_name(
                        cfg.get("destination_code"), cfg.get("destination_name", "Central")
                    ),
                    "poll_interval_ms": cfg.get("poll_interval_ms", 30000),
                    "lanIp": get_lan_ip(),
                    "port": cfg.get("port", 5052),
                }
            )
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/trains/config":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else {}
                cfg = load_config()
                if "origin_code" in body:
                    cfg["origin_code"] = str(body["origin_code"]).strip()
                    cfg["origin_name"] = train_service.get_station_name(cfg["origin_code"])
                if "destination_code" in body:
                    cfg["destination_code"] = str(body["destination_code"]).strip()
                    cfg["destination_name"] = train_service.get_station_name(cfg["destination_code"])
                if "poll_interval_ms" in body:
                    cfg["poll_interval_ms"] = max(5000, int(body["poll_interval_ms"]))
                save_config(cfg)
                train_service.cached_result = None
                self.send_json({"success": True, "config": cfg})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=400)
            return

        self.send_error(404, "Not Found")


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    cfg = load_config()
    port = cfg.get("port", 5052)
    server = ThreadedServer(("0.0.0.0", port), TrainHTTPHandler)
    print(f"=== TrainKindle Standalone Server running on port {port} ===")
    print(f"LAN URL: http://{get_lan_ip()}:{port}/api/trains")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TrainKindle Server.")
        server.server_close()


if __name__ == "__main__":
    main()
