from flask import Flask, render_template, request
import os
import re

app = Flask(__name__)

LOG_PATH = "final_logs.txt.txt"


def extract_pallet_id(line):
    """Find any 8-digit pallet ID in the line."""
    match = re.search(r"\b(\d{8})\b", line)
    return match.group(1) if match else ""


def parse_logs():
    """Get the latest 10 ARRIVAL, SETDEST, EXIT messages."""
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


def get_pallet_history(pallet_id):
    """Return every event that involves the selected pallet."""
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
            event = parts[1].strip().strip(".")
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""

            if event == "SETDEST" and not to and len(parts) > 4:
                to = parts[4].strip()

            history.append((step_no, event, frm, to))
            step_no += 1

    return history


@app.route("/")
def index():
    arrivals, setdest, exits = parse_logs()

    selected = request.args.get("pallet_id", "").strip()
    history = get_pallet_history(selected) if selected else []

    # Determine pallet status
    current_location = ""
    next_destination = ""
    status = ""

    if history:
        last = history[-1]
        _, event, frm, to = last

        if event == "ARRIVAL":
            status = "Arrived"
            current_location = frm

        elif event == "SETDEST":
            status = "Moving"
            current_location = frm
            next_destination = to

        elif event == "LOCEXIT":
            status = "Exited"
            current_location = frm

    return render_template(
        "index.html",
        arrivals=arrivals,
        setdest=setdest,
        exits=exits,
        searched_id=selected,
        history=history,
        current_location=current_location,
        next_destination=next_destination,
        status=status
    )


if __name__ == "__main__":
    app.run(debug=True)
    
