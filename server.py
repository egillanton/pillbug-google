from flask import Flask, request, render_template, jsonify
from argparse import ArgumentParser
from scripts import google
import os
import json

# Init Flask App
app = Flask(__name__)
app.secret_key = os.urandom(12)  # Generic key for dev purposes only

# ======== Routing =========================================================== #
# -------- Home ---------------------------------------------------------- #
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


# -------- Send ---------------------------------------------------------- #
@app.route('/remind', methods=['GET', 'POST'])
def reminders():
    if request.method == 'POST':
        title = request.json['title']
        time_str = request.json['time_str']

        reminder = google.remind(title, time_str)

        return jsonify(
            response=str(reminder),
        )
    else:
        num_reminders = request.args['n']
        client = google.RemindersClient()
        text = ""
        reminders = client.list_reminders(num_reminders=num_reminders)
        if reminders is not None:
            for r in sorted(reminders):
                text += f'{r}\n'

        return jsonify(
            response=text,
        )


# ======== Main ============================================================== #
if __name__ == '__main__':
    parser = ArgumentParser(description='Example Flask Application')
    parser.add_argument("-p", "--port", type=int,
                        metavar="PORT", dest="port", default=5000, help='Port number')
    parser.add_argument("--host", type=str, metavar="HOST",
                        dest="host", default="localhost")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=True)
