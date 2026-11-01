import os, sys, json, time, random, argparse, urllib.request, urllib.error
import psycopg2, psycopg2.extras

API = os.environ.get("API_URL", "http://127.0.0.1:5000/api/iot/event")
TOKEN = os.environ.get("DEVICE_TOKEN", "dev-device-token")
DB_URL = os.environ.get("DATABASE_URL", "dbname=docrequest user=postgres password=12345 host=localhost")


def send(locker_id, event_type, request_id=None, battery=None):
    body = json.dumps({"locker_id": locker_id, "event_type": event_type, "request_id": request_id, "battery_pct": battery}).encode()
    req = urllib.request.Request(API, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Device-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def read_world():
    """lockers, occupancy (locker -> request id or None) and Ready requests that are not placed yet"""
    con = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT locker_id, label FROM lockers ORDER BY locker_id"); lockers = cur.fetchall()
            cur.execute("""SELECT DISTINCT ON (locker_id) locker_id, event_type, request_id FROM locker_events
                           WHERE event_type IN ('document_present', 'document_removed')
                           ORDER BY locker_id, created_at DESC, event_id DESC""")
            occupied = {r["locker_id"]: r["request_id"] for r in cur.fetchall() if r["event_type"] == "document_present"}
            cur.execute("""SELECT r.request_id, l.locker_id FROM requests r JOIN lockers l ON l.point_id = r.pickup_point_id
                           WHERE r.status = 'Ready' AND NOT EXISTS (SELECT 1 FROM locker_events e
                                 WHERE e.request_id = r.request_id AND e.event_type = 'document_present')""")
            to_place = cur.fetchall()
    finally:
        con.close()
    return lockers, occupied, to_place


def plan(rnd, occupied, to_place):
    """decide at most one action in this tick: ('place'|'collect', locker_id, request_id) or None"""
    free = [r for r in to_place if r["locker_id"] not in occupied]
    if free and rnd.random() < 0.5:
        r = rnd.choice(free); return ("place", r["locker_id"], r["request_id"])
    if occupied and rnd.random() < 0.4:
        locker_id = rnd.choice(sorted(occupied)); return ("collect", locker_id, occupied[locker_id])
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--ticks", type=int, default=0); ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(); rnd = random.Random(a.seed); battery = {}; tick = 0
    print(f"simulating cabinets -> {API} every {a.interval} s (Ctrl+C to stop)")
    while a.ticks == 0 or tick < a.ticks:
        tick += 1
        lockers, occupied, to_place = read_world()
        for l in lockers:
            battery.setdefault(l["locker_id"], rnd.randint(70, 100))
            if rnd.random() < 0.1: battery[l["locker_id"]] = max(5, battery[l["locker_id"]] - 1)
            code = send(l["locker_id"], "heartbeat", battery=battery[l["locker_id"]])
            if code != 201: print(f"  heartbeat of {l['label']} rejected: HTTP {code}"); 
        act = plan(rnd, occupied, to_place)
        if act:
            kind, locker_id, request_id = act
            label = next(l["label"] for l in lockers if l["locker_id"] == locker_id)
            middle = "document_present" if kind == "place" else "document_removed"
            for ev, rid in (("door_opened", None), (middle, request_id), ("door_closed", None)):
                send(locker_id, ev, request_id=rid); time.sleep(0.3)
            print(f"[{time.strftime('%H:%M:%S')}] {label}: document of request #{request_id} " + ("placed" if kind == "place" else "collected"))
        else:
            print(f"[{time.strftime('%H:%M:%S')}] tick {tick}: heartbeats sent for {len(lockers)} cabinets")
        time.sleep(a.interval)


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("stopped")
