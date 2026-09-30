"""Headless end-to-end check.

Loads the real page in headless Chrome, types a phrase, clicks the generate
button, and asserts the output panel actually fills in.

    .venv/bin/python e2e_check.py
"""

import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

PORT = int(os.environ.get("PORT", "5001"))
CHROME = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
BASE = f"http://127.0.0.1:{PORT}"
PHRASE = "мы ночуем в палатке у самой реки"


def check_api() -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/generate",
        data=json.dumps({"phrase": PHRASE}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def check_browser() -> None:
    url = f"{BASE}/__e2e__?phrase=" + urllib.parse.quote(PHRASE)
    out = subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--virtual-time-budget=25000", "--dump-dom", url,
        ],
        capture_output=True, text=True, timeout=180,
    )

    # --dump-dom escapes '>' as &gt;, so unescape before looking for the markers.
    match = re.search(r"<title>(.*?)</title>", out.stdout, re.S)
    title = html.unescape(match.group(1)) if match else ""
    if "OUT>>" not in title:
        print("FAIL: output panel never filled in")
        print(out.stdout[:400])
        sys.exit(1)

    payload = title
    text = payload.split("|META>>")[0].replace("OUT>>", "").strip()
    meta = payload.split("|META>>")[1].split("|STATUS>>")[0]
    status = payload.split("|STATUS>>")[1].strip()

    print("  status :", status)
    print("  meta   :", meta[:90])
    print("  output :", text[:100], "...")
    if len(text) < 40:
        print("FAIL: output panel suspiciously short")
        sys.exit(1)


def main() -> None:
    data = check_api()
    print("API")
    print("  keyword :", data["keyword_de"], f"({data['match_count']} matches)")
    print("  source  :", data["source_de"])
    print("  russian :", data["text"][:100], "...")

    assert data["text"].strip(), "FAIL: empty text"
    for word in ("Haschisch", "Opium"):
        assert word not in data["text"], f"FAIL: uncensored {word} leaked"
    for frame in ("Я девочка", "Я девушка", "Я девчонка"):
        assert frame not in data["text"], f"FAIL: frame {frame!r} not stripped"
    print("  checks  : non-empty, censored, gender frame stripped")

    print()
    print("BROWSER")
    check_browser()
    print()
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
