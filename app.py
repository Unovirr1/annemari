"""Web front-end for the 'Glueckliche Tal' text generator.

Run with:  .venv/bin/python app.py
Then open:  http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import threading
import traceback
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import annemarie_core as core

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

HIT_COUNT_FILE = os.path.join(core.BASE_DIR, ".hits.json")


def _bump_hits() -> int:
    """Persist a visit counter the way a 1995 guestbook counter would."""
    count = 0
    try:
        with open(HIT_COUNT_FILE, "r", encoding="utf-8") as handle:
            count = int(json.load(handle).get("count", 0))
    except (OSError, ValueError, TypeError):
        count = 0
    count += 1
    try:
        with open(HIT_COUNT_FILE, "w", encoding="utf-8") as handle:
            json.dump({"count": count}, handle)
    except OSError:
        pass
    return count


def _warm_cache() -> None:
    """Parse the PDF in the background so the first visitor isn't punished."""
    try:
        core.get_sentences()
    except Exception:
        traceback.print_exc()


@app.route("/")
def index():
    try:
        stats = core.corpus_stats()
    except Exception:
        traceback.print_exc()
        stats = {"sentences": 0, "source": "?"}
    return render_template(
        "index.html",
        hits=_bump_hits(),
        sentences=stats["sentences"],
        source=stats["source"],
        year=datetime.now().year,
    )


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(silent=True) or {}
    phrase = payload.get("phrase", "")
    if not isinstance(phrase, str) or not phrase.strip():
        return jsonify({"error": "Пустая фраза. Напишите что-нибудь!"}), 400
    try:
        return jsonify(core.generate_sync(phrase))
    except Exception as exc:  # surfaced in the status bar, like a 502 would be
        traceback.print_exc()
        return jsonify({"error": str(exc) or exc.__class__.__name__}), 502


@app.route("/api/corpus")
def api_corpus():
    try:
        return jsonify(core.corpus_stats())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# --------------------------------------------------------------------------- #
# Test-only harness.  Enabled with E2E=1, so it never exists in normal use.
# e2e_check.py needs a same-origin page to drive the real UI from.
# --------------------------------------------------------------------------- #
if os.environ.get("E2E") == "1":

    @app.route("/__e2e__")
    def e2e_probe():
        phrase = request.args.get("phrase", "мы ночуем в палатке у самой реки")
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>pending</title></head><body>loading
<iframe id="f" width="700" height="900" src="/"></iframe>
<script>
window.addEventListener('load', function () {{
  var d = document.getElementById('f').contentWindow.document;
  d.getElementById('phrase').value = {json.dumps(phrase, ensure_ascii=False)};
  d.defaultView.generate();
  setTimeout(function () {{
    document.title = 'OUT>>' + d.getElementById('out').textContent
      + '|META>>' + d.getElementById('outmeta').textContent
      + '|STATUS>>' + d.getElementById('status').textContent;
  }}, 9000);
}});
</script></body></html>"""


def _free_port(start: int) -> int:
    """Walk forward from `start` until we find a port nobody is holding."""
    import socket

    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"Нет свободного порта в диапазоне {start}-{start + 19}")


if __name__ == "__main__":
    # PORT wins if set; otherwise start at 5000 and slide past anything taken
    # (the weather_proj app in the sibling folder usually owns 5000).
    port = (
        int(os.environ["PORT"])
        if os.environ.get("PORT")
        else _free_port(5000)
    )
    # PaaS hosts (Render/Railway/Fly/...) inject PORT and need 0.0.0.0;
    # local runs stay on loopback.
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    threading.Thread(target=_warm_cache, name="corpus-warm", daemon=True).start()
    print(f"* Счастливая Долина: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
