from flask import Flask, jsonify
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from statistics import mean
import json

app = Flask(__name__)
CORS(app)

# ----------------------------------------
# Paths to data files
# ----------------------------------------
BASE_DIR = Path(__file__).parent.parent  # project folder
DATA_DIR = BASE_DIR / "data"
LOG_PATH = DATA_DIR / "logs.txt"         # change if your file name is different
LAYOUT_PATH = DATA_DIR / "layout.json"


# ----------------------------------------
# Log parsing and movement history
# ----------------------------------------

def parse_real_log_line(line: str):
    """
    Parse one line from the Dematic-style log file.
    Example:
    08-12-25 08:25:42.818  ~PLC1WMS1...ARRIVAL..NOTIPOINT01..NOTIPOINT02....10000000...##
    I only care about ARRIVAL events with from/to locations.
    """
    line = line.strip()
    if not line:
        return None

    parts = line.split()
    if len(parts) < 3:
        return None

    date_str = parts[0]  # e.g. 08-12-25 (yy-mm-dd)
    time_str = parts[1]  # e.g. 08:25:42.818

    try:
        timestamp = datetime.strptime(
            date_str + " " + time_str,
            "%y-%m-%d %H:%M:%S.%f"
        )
    except ValueError:
        # timestamp didn't parse properly, so I’m ignoring this entry
        return None

    # the log usually puts the message part after a double space
    if "  " in line:
        rest = line.split("  ", 1)[1]
    else:
        # backup way of getting the message part if the split isn’t standard
        rest = " ".join(parts[2:])

    # these logs use ".." as separators
    raw_tokens = rest.split("..")

    cleaned = []
    for t in raw_tokens:
        t = t.replace(".", "").strip()
        if t:
            cleaned.append(t)

    # cleaned should look like:
    # ['~PLC1WMS1', 'ARRIVAL', 'NOTIPOINT01', 'NOTIPOINT02', '10000000', '##']
    if len(cleaned) < 3:
        return None

    system_name = cleaned[0]
    event_type = cleaned[1].upper()

    # only using ARRIVAL for movement
    if event_type != "ARRIVAL":
        return None

    from_loc = cleaned[2] if len(cleaned) > 2 else None
    to_loc = None
    if len(cleaned) > 3 and not cleaned[3].isdigit():
        to_loc = cleaned[3]

    # if there's no destination, I can't use this as a movement event
    if not from_loc or not to_loc:
        return None

    # pallet ID = last numeric token
    pallet_id = None
    for token in reversed(cleaned):
        if token.isdigit():
            pallet_id = token
            break

    if pallet_id is None:
        return None

    return {
        "time": timestamp,
        "event": event_type,
        "from": from_loc,
        "to": to_loc,
        "palletId": pallet_id
    }


def load_events():
    """
    Read the log file and return a list of ARRIVAL events
    that have from/to locations.
    """
    events = []
    text = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()

    for line in text:
        evt = parse_real_log_line(line)
        if evt is not None:
            events.append(evt)

    events.sort(key=lambda e: e["time"])
    return events


def group_events_by_pallet(events):
    """
    Put events into a dictionary by palletId:
    { palletId: [event1, event2, ...] }
    """
    by_pallet = defaultdict(list)

    for e in events:
        pid = e["palletId"]
        by_pallet[pid].append(e)

    for pid in by_pallet:
        by_pallet[pid].sort(key=lambda e: e["time"])

    return by_pallet


def compute_travel_times(events_by_pallet):
    """
    For each pallet, look at consecutive ARRIVAL events and treat
    the time between them as the travel time for the edge of the
    current event: from -> to.
    Then average those times for each edge.
    Returns a dict: { "FROM->TO": avg_seconds }
    """
    durations_by_edge = defaultdict(list)

    for pid, p_events in events_by_pallet.items():
        if len(p_events) < 2:
            continue

        for i in range(1, len(p_events)):
            prev_evt = p_events[i - 1]
            curr_evt = p_events[i]

            dt = (curr_evt["time"] - prev_evt["time"]).total_seconds()
            if dt <= 0:
                continue

            edge_key = f"{curr_evt['from']}->{curr_evt['to']}"
            durations_by_edge[edge_key].append(dt)

    travel_times = {}
    for edge_key, durations in durations_by_edge.items():
        # not handling outliers yet — just using the average travel time
        travel_times[edge_key] = mean(durations)

    return travel_times


# ----------------------------------------
# Simulation of live movement
# ----------------------------------------

class Simulation:
    """
    Simple simulation that replays ARRIVAL movements over time.
    For each ARRIVAL with from/to, we treat it as a move starting at event time
    and lasting travel_times[from->to] seconds (or a default).
    """

    def __init__(self, events, travel_times, default_travel_seconds=5):
        self.events = events
        self.travel_times = travel_times
        self.default_travel_seconds = default_travel_seconds

        if self.events:
            self.sim_time = self.events[0]["time"]
        else:
            self.sim_time = datetime.now()

        self.sim_index = 0
        # palletId -> state dict
        self.pallet_state = {}

    def advance_time(self, delta_seconds):
        """
        Move simulated time forward and apply any events that
        should have happened by now.
        """
        self.sim_time += timedelta(seconds=delta_seconds)

        while self.sim_index < len(self.events) and \
                self.events[self.sim_index]["time"] <= self.sim_time:

            e = self.events[self.sim_index]
            pid = e["palletId"]

            edge_key = f"{e['from']}->{e['to']}"
            avg_secs = self.travel_times.get(edge_key, self.default_travel_seconds)

            move_start = e["time"]
            expected_arrival = move_start + timedelta(seconds=avg_secs)

            # store the latest state for this pallet
            self.pallet_state[pid] = {
                "movingFrom": e["from"],
                "movingTo": e["to"],
                "moveStart": move_start,
                "expectedArrival": expected_arrival,
                "currentLocation": e["to"]  # last known destination
            }

            self.sim_index += 1

    def step(self, delta_seconds=2):
        """
        Move time forward and return a snapshot of the current state.
        """
        self.advance_time(delta_seconds)

        snapshot = {
            "simTime": self.sim_time,
            "pallets": []
        }

        for pid, state in self.pallet_state.items():
            pallet_info = {"palletId": pid}
            pallet_info.update(state)
            snapshot["pallets"].append(pallet_info)

        return snapshot


# ----------------------------------------
# Load layout + events at startup
# ----------------------------------------

try:
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    layout = {"floors": [], "edges": []}

events = load_events()
events_by_pallet = group_events_by_pallet(events)
travel_times = compute_travel_times(events_by_pallet)

sim = Simulation(events, travel_times, default_travel_seconds=5)


# ----------------------------------------
# Helper for datetime → string
# ----------------------------------------

def serialize_time(dt: datetime | None):
    if dt is None:
        return None
    return dt.isoformat()


# ----------------------------------------
# Flask routes / JSON APIs
# ----------------------------------------

@app.route("/")
def home():
    return "Backend is running. Try /api/health, /api/layout or /api/state"


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "eventsLoaded": len(events)})


@app.route("/api/layout")
def get_layout():
    return jsonify(layout)


@app.route("/api/state")
def get_state():
    """
    Frontend should call this regularly (e.g. every 1 second).
    Each call moves the simulation forward and returns pallet states.
    """
    snapshot = sim.step(delta_seconds=2)

    output_pallets = []
    for p in snapshot["pallets"]:
        output_pallets.append({
            "palletId": p["palletId"],
            "movingFrom": p["movingFrom"],
            "movingTo": p["movingTo"],
            "moveStart": serialize_time(p["moveStart"]),
            "expectedArrival": serialize_time(p["expectedArrival"]),
            "currentLocation": p["currentLocation"]
        })

    return jsonify({
        "simTime": serialize_time(snapshot["simTime"]),
        "pallets": output_pallets
    })


if __name__ == "__main__":
    print("Using log file:", LOG_PATH)
    print("Total events loaded:", len(events))
    app.run(debug=True)
