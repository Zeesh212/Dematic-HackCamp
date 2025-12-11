from flask import Flask, render_template, request, jsonify
import os
import re

app = Flask(__name__)

LOG_PATH = "final_logs.txt.txt"


def extract_pallet_id(line):
    match = re.search(r"\b(\d{8})\b", line)
    return match.group(1) if match else ""


def parse_all_events():
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

            pallet = extract_pallet_id(line)

            rec = {
                "timestamp": timestamp,
                "event": event,
                "from": frm,
                "to": to,
                "pallet": pallet
            }
            events.append(rec)

            if "FAULT" in event.upper():
                faults.append(rec)

    return events, faults


def get_pallet_history(pallet_id):
    if not pallet_id or not os.path.exists(LOG_PATH):
        return []

    history = []
    step = 1

    with open(LOG_PATH, "r") as f:
        for line in f:
            if extract_pallet_id(line) != pallet_id:
                continue

            parts = line.split("..")
            if len(parts) < 2:
                continue

            event = parts[1].strip().strip(".")
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""

            if event == "SETDEST" and not to and len(parts) > 4:
                to = parts[4].strip()

            history.append((step, event, frm, to))
            step += 1

    return history


def build_pallet_states(events):
    pallet_states = {}
    first_seen = {}

    for rec in events:
        pallet = rec["pallet"]
        if not pallet:
            continue

        if pallet not in first_seen:
            first_seen[pallet] = rec["timestamp"]

        event = rec["event"]
        frm = rec["from"]
        to = rec["to"]

        state = pallet_states.get(pallet, {
            "pallet": pallet,
            "current_location": "",
            "next_destination": "",
            "status": "Unknown",
            "exited": False,
        })

        if event == "SETDEST":
            state["status"] = "Moving"
            state["current_location"] = frm or state["current_location"]
            state["next_destination"] = to

        elif event == "ARRIVAL":
            if to.startswith("OUTPOINT"):
                state["status"] = "Exited"
                state["current_location"] = to
                state["next_destination"] = ""
                state["exited"] = True
            else:
                state["status"] = "Arrived"
                state["current_location"] = to or frm

        elif event == "LOCEXIT":
            state["status"] = "Exited"
            state["current_location"] = frm
            state["next_destination"] = ""
            state["exited"] = True

        pallet_states[pallet] = state

    active = [p for p, st in pallet_states.items() if not st["exited"]]
    active.sort(key=lambda p: first_seen[p])

    current = active[0] if active else None
    nxt = active[1] if len(active) > 1 else None

    return pallet_states, current, nxt


@app.route("/pallet_path/<pallet_id>")
def pallet_path(pallet_id):
    history = get_pallet_history(pallet_id)
    if not history:
        return jsonify({"error": "Not found"}), 404

    visited = []
    for _, event, frm, to in history:
        if event in ("ARRIVAL", "SETDEST") and to:
            visited.append(to)

    return jsonify({
        "pallet": pallet_id,
        "visited": visited,
        "current": visited[-1] if visited else None
    })


@app.route("/all_pallet_positions")
def all_pallet_positions():
    events, _ = parse_all_events()

    positions = {}
    for rec in events:
        pallet = rec["pallet"]
        if not pallet:
            continue

        event = rec["event"]
        frm = rec["from"]
        to = rec["to"]

        if event == "ARRIVAL" and to:
            positions[pallet] = to
        elif event == "SETDEST" and to:
            positions[pallet] = to

    return jsonify(positions)


@app.route("/")
def index():
    events, faults = parse_all_events()
    pallet_states, current_pallet_id, next_pallet_id = build_pallet_states(events)

    selected = request.args.get("pallet_id", "").strip()

    history = get_pallet_history(selected) if selected else []

    selected_state = pallet_states.get(selected) if selected else None

    current_location = selected_state["current_location"] if selected_state else ""
    next_destination = selected_state["next_destination"] if selected_state else ""
    status = selected_state["status"] if selected_state else ""

    latest_events = events[-80:]
    latest_faults = faults[-10:]

    pallet_summary = sorted(
        [s for s in pallet_states.values() if not s["exited"]],
        key=lambda s: s["pallet"]
    )

    return render_template(
        "index.html",
        searched_id=selected,
        history=history,
        current_location=current_location or "Unknown",
        next_destination=next_destination or "Unknown",
        status=status or "Unknown",
        latest_events=latest_events,
        pallet_summary=pallet_summary,
        current_pallet_id=current_pallet_id,
        next_pallet_id=next_pallet_id,
        latest_faults=latest_faults
    )


if __name__ == "__main__":
    app.run(debug=True)
    

