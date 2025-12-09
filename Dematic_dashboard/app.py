from flask import Flask, render_template, request, jsonify
import os
import re

app = Flask(__name__)

LOG_PATH = "final_logs.txt.txt"


def extract_pallet_id(line):
    """Return the first 8-digit pallet ID found in a log line, or empty string."""
    match = re.search(r"\b(\d{8})\b", line)
    return match.group(1) if match else ""


def parse_logs():
    """
    Older helper that groups by event type.
    Left in place in case you still want to inspect ARRIVAL / SETDEST / EXIT
    separately while developing.
    """
    arrivals = []
    setdest = []
    exits = []

    if not os.path.exists(LOG_PATH):
        return arrivals, setdest, exits

    with open(LOG_PATH, "r") as f:
        for line in f:
            parts = line.split("..")
            if len(parts) < 2:
                continue

            event = parts[1].strip().strip(".")
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""

            if event == "SETDEST" and not to and len(parts) > 4:
                to = parts[4].strip()

            pallet_id = extract_pallet_id(line)

            if "ARRIVAL" in event:
                arrivals.append((event, frm, to, pallet_id))
            elif "SETDEST" in event:
                setdest.append((event, frm, to, pallet_id))
            elif "LOCEXIT" in event or "OUTPOINT" in frm or "OUTPOINT" in to:
                exits.append((event, frm, to, pallet_id))

    return arrivals[-10:], setdest[-10:], exits[-10:]


def parse_all_events():
    """
    Build a chronological list of events from the log file.
    Each event is a dict so it’s easy to show in the template.
    """
    events = []
    faults = []

    if not os.path.exists(LOG_PATH):
        return events, faults

    with open(LOG_PATH, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("..")
            if len(parts) < 2:
                continue

            timestamp = parts[0].strip()
            event = parts[1].strip().strip(".")
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""

            if event == "SETDEST" and not to and len(parts) > 4:
                to = parts[4].strip()

            pallet_id = extract_pallet_id(line)

            rec = {
                "timestamp": timestamp,
                "event": event,
                "from": frm,
                "to": to,
                "pallet": pallet_id,
            }
            events.append(rec)

            if "FAULT" in event.upper():
                faults.append(rec)

    return events, faults


def get_pallet_history(pallet_id):
    """
    All events for a single pallet, in order.
    Returned as (step_no, event, from, to).
    """
    if not pallet_id or not os.path.exists(LOG_PATH):
        return []

    history = []
    step_no = 1

    with open(LOG_PATH, "r") as f:
        for line in f:
            found_id = extract_pallet_id(line)
            if found_id != pallet_id:
                continue

            parts = line.split("..")
            if len(parts) < 2:
                continue

            event = parts[1].strip().strip(".")
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""

            if event == "SETDEST" and not to and len(parts) > 4:
                to = parts[4].strip()

            history.append((step_no, event, frm, to))
            step_no += 1

    return history


def build_pallet_states(events):
    """
    From the flat event list, work out the current state of each pallet:
    - status
    - current location
    - next destination
    Also decide which pallet is "current" and which is "next".
    """
    pallet_states = {}
    first_seen = {}

    for rec in events:
        pallet_id = rec.get("pallet")
        if not pallet_id:
            continue

        if pallet_id not in first_seen:
            first_seen[pallet_id] = rec.get("timestamp")

        event = rec.get("event", "")
        frm = rec.get("from", "") or ""
        to = rec.get("to", "") or ""

        state = pallet_states.get(
            pallet_id,
            {
                "pallet": pallet_id,
                "current_location": "",
                "next_destination": "",
                "status": "Unknown",
                "exited": False,
            },
        )

        if event == "SETDEST":
            state["status"] = "Moving"
            state["current_location"] = frm or state.get("current_location", "")
            state["next_destination"] = to

        elif event == "ARRIVAL":
        
            if to and to.startswith("OUTPOINT"):
                state["status"] = "Exited"
                state["current_location"] = to
                state["next_destination"] = ""
                state["exited"] = True
            else:
                state["status"] = "Arrived"
                state["current_location"] = to or frm or state.get(
                    "current_location", ""
                )

        elif event == "LOCEXIT":
            state["status"] = "Exited"
            state["current_location"] = frm or state.get("current_location", "")
            state["next_destination"] = ""
            state["exited"] = True

        pallet_states[pallet_id] = state

    active_ids = [pid for pid, st in pallet_states.items() if not st.get("exited")]
    active_ids.sort(key=lambda pid: first_seen.get(pid, ""))

    current_pallet_id = active_ids[0] if active_ids else None
    next_pallet_id = active_ids[1] if len(active_ids) > 1 else None

    return pallet_states, current_pallet_id, next_pallet_id


@app.route("/pallet_path/<pallet_id>")
def pallet_path(pallet_id):
    """JSON representation of a pallet's path, used by the front-end animation."""
    history = get_pallet_history(pallet_id)
    if not history:
        return jsonify({"error": "Not found"}), 404

    visited = []

    for _, event, frm, to in history:
        if event == "ARRIVAL" and to:
            visited.append(to)
        elif event == "SETDEST" and to:
            visited.append(to)

    return jsonify(
        {
            "pallet": pallet_id,
            "visited": visited,
            "current": visited[-1] if visited else None,
        }
    )


@app.route("/")
def index():
    events, faults = parse_all_events()
    pallet_states, current_pallet_id, next_pallet_id = build_pallet_states(events)

    latest_events = events[-80:]

    selected = request.args.get("pallet_id", "").strip()
    history = get_pallet_history(selected) if selected else []

    selected_state = pallet_states.get(selected) if selected else None

    current_location = ""
    next_destination = ""
    status = ""

    if selected_state:
        current_location = selected_state.get("current_location") or "Unknown"
        next_destination = selected_state.get("next_destination") or "Unknown"
        status = selected_state.get("status") or "Unknown"
    elif selected:
        
        status = "Not found"
        current_location = "Unknown"
        next_destination = "Unknown"

    pallet_summary = sorted(
        [s for s in pallet_states.values() if not s.get("exited")],
        key=lambda s: s.get("pallet", ""),
    )

    latest_faults = faults[-10:]

    return render_template(
        "index.html",
        searched_id=selected,
        history=history,
        current_location=current_location,
        next_destination=next_destination,
        status=status,
        latest_events=latest_events,
        pallet_summary=pallet_summary,
        current_pallet_id=current_pallet_id,
        next_pallet_id=next_pallet_id,
        latest_faults=latest_faults,
    )


if __name__ == "__main__":
    app.run(debug=True)
