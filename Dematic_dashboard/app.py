from flask import Flask, render_template, request
import os

app = Flask(__name__)

LOG_PATH = "final_logs.txt.txt"


def parse_logs():
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

            event = parts[1].strip().strip(".")  # ARRIVAL, SETDEST, LOCEXIT etc.
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""

            if event == "SETDEST" and not to and len(parts) > 4:
                to = parts[4].strip()

            pallet_id = ""
            for word in line.split():
                if word.isdigit() and len(word) == 8:
                    pallet_id = word
                    break

            if "ARRIVAL" in event:
                arrivals.append((event, frm, to, pallet_id))
            elif "SETDEST" in event:
                setdest.append((event, frm, to, pallet_id))
            elif "LOCEXIT" in event or "OUTPOINT" in frm or "OUTPOINT" in to:
                exits.append((event, frm, to, pallet_id))

    return arrivals[-10:], setdest[-10:], exits[-10:]


def get_pallet_history(pallet_id: str):
    """
    Return full history for a given pallet id:
    list of (step_no, event, from, to).
    """
    history = []

    if not pallet_id or not os.path.exists(LOG_PATH):
        return history

    step_no = 1

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

            found_id = ""
            for word in line.split():
                if word.isdigit() and len(word) == 8:
                    found_id = word
                    break

            if found_id == pallet_id:
                history.append((step_no, event, frm, to))
                step_no += 1

    return history


@app.route("/")
def index():
    # Live view data
    arrivals, setdest, exits = parse_logs()

    # Optional pallet history
    searched_id = request.args.get("pallet_id", "").strip()
    history = get_pallet_history(searched_id) if searched_id else []

    return render_template(
        "index.html",
        arrivals=arrivals,
        setdest=setdest,
        exits=exits,
        searched_id=searched_id,
        history=history,
    )


if __name__ == "__main__":
    app.run(debug=True)


