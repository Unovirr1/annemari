"""Censorship check: the book's drug words must be blacked out whenever the
book text mentions them.

Three layers:
  1. unit      - censor() replaces words, _squash_blocks() glues █ runs back
  2. forced    - a German sentence that contains Haschisch/Opium (taken from
                 the PDF itself) is censored and translated; blocks must come
                 out and no drug word may leak
  3. app+browser - phrase whose keyword IS "Haschisch" (so matched sentences
                 mention it): the live page must show blocks, never the words

    .venv/bin/python censor_check.py
"""

import html
import json
import os
import random
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import annemarie_core as core

PORT = int(os.environ.get("PORT", "5001"))
CHROME = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
BASE = f"http://127.0.0.1:{PORT}"
PHRASE = "я хочу найти гашиш в долине"  # DE keyword comes out as "Haschisch"
FORBIDDEN = ("Haschisch", "Opium", "гашиш", "опиум",
             "гашиша", "опиума", "гашишем", "опиумом")

passed = 0
failed = 0


def report(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    print(f"  {name:12s}: {'PASS' if ok else 'FAIL'}  {detail}")
    if ok:
        passed += 1
    else:
        failed += 1


def check_unit() -> None:
    censored = core.censor("Wir rauchen Opium und Haschisch")
    report("unit censor", censored == "Wir rauchen \u2588\u2588\u2588\u2588\u2588 und \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588",
           repr(censored))

    squashed = core._squash_blocks("a \u2588 \u2588 \u2588 b")
    report("unit squash", squashed == "a\u2588b", repr(squashed))


def check_forced() -> None:
    """A real book sentence mentioning the drugs, run through the pipeline."""
    sentences = core.get_sentences()
    drug_sentence = random.choice([s for s in sentences if "Haschisch" in s or "Opium" in s])
    composed = core.censor(drug_sentence)  # what generate(composed) now does
    ru = core.run_sync(
        core.translate("ich bin ein Mädchen, " + composed, src="de", dest="ru")
    )
    ru = core._squash_blocks(core.censor(ru))
    leaked = sorted({w for w in FORBIDDEN if w in ru})
    report("forced dark", ("█" in ru) and not leaked,
           f"blocks={('█' in ru)} leaked={leaked or 'none'} :: {ru[:100]}")


def check_api() -> None:
    req = urllib.request.Request(
        f"{BASE}/api/generate",
        data=json.dumps({"phrase": PHRASE}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)
    text = data["text"]
    leaked = sorted({w for w in FORBIDDEN if w in text})

    # Keyword must be Haschisch for this phrase to be meaningful.
    report("api keyword", data["keyword_de"].lower() == "haschisch",
           f"kw={data['keyword_de']!r}")
    report("api dark", "█" in text and not leaked,
           f"blocks={('█' in text)} leaked={leaked or 'none'}")


def check_browser() -> None:
    url = f"{BASE}/__e2e__?phrase=" + urllib.parse.quote(PHRASE)
    out = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=25000", "--dump-dom", url],
        capture_output=True, text=True, timeout=180,
    )
    match = re.search(r"<title>(.*?)</title>", out.stdout, re.S)
    title = html.unescape(match.group(1)) if match else ""
    text = title.split("|META>>")[0].replace("OUT>>", "").strip()
    report("browser dark", "█" in text and not any(w in text for w in FORBIDDEN),
           f"{text[:90]}")


def main() -> int:
    print("PHRASE:", PHRASE)
    check_unit()
    check_forced()
    check_api()
    check_browser()
    print()
    if failed:
        print(f"{passed} passed, {failed} FAILED")
        return 1
    print("CENSORSHIP CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())