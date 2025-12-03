from flask import Flask, render_template_string

LOG_PATH = "final_logs.txt.txt"

app = Flask(__name__)

def parse_logs():
    arrivals = []
    setdest = []
    exits = []

    with open(LOG_PATH, "r") as f:
        for line in f:
            parts = line.split("..")
            event = parts[1].strip()
            frm = parts[2].strip() if len(parts) > 2 else ""
            to = parts[3].strip() if len(parts) > 3 else ""
            
            pallet_id = ""
            for word in line.split():
                if word.isdigit() and len(word) == 8:
                    pallet_id = word

            if "ARRIVAL" in event:
                arrivals.append((event, frm, to, pallet_id))

            elif "SETDEST" in event:
                setdest.append((event, frm, to, pallet_id))

            elif "LOCEXIT" in event or "OUTPOINT" in frm or "OUTPOINT" in to:
                exits.append((event, frm, to, pallet_id))

    return arrivals[-10:], setdest[-10:], exits[-10:]


def make_table(data):
    html = "<table><tr><th>Event</th><th>From</th><th>To</th><th>Pallet</th></tr>"
    for e, f, t, p in data:
        html += f"<tr><td>{e}</td><td>{f}</td><td>{t}</td><td>{p}</td></tr>"
    html += "</table>"
    return html


@app.route("/")
def index():
    arrivals, setdest, exits = parse_logs()

    with open("index.html") as f:
        template = f.read()

    return render_template_string(template,
        arrivals=make_table(arrivals),
        setdest=make_table(setdest),
        exits=make_table(exits)
    )


if __name__ == "__main__":
    app.run(debug=True)
