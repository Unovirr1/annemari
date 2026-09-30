"""Core logic for the 'Glueckliche Tal' generator.

Extracted from annemarie_v2.py (the console version) so the same behaviour can
be driven by the web front-end.  Everything that used to run in ``main()`` now
lives in importable helpers, and the text-only work is wrapped in a thread pool
because pypdf parsing and pymorphy3 calls are CPU bound and would otherwise
block the Flask event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import pymorphy3
from googletrans import Translator
from pypdf import PdfReader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(
    BASE_DIR, "annemarie-schwarzenbach-das-glueckliche-tal.pdf"
)
CACHE_PATH = os.path.join(BASE_DIR, ".corpus_cache.json")

# The original script blacked these out in the German source *before*
# translating, so the block characters flow straight into the Russian result.
# The Russian spellings are caught too in case the translator spells them out
# anyway.  Block counts match the letter counts, as in annemarie_v2.py.
CENSORED = {
    "Haschisch": 9,
    "Opium": 5,
    "гашиш": 5,
    "опиум": 5,
}
PUNCTUATION = '!_#$%\'()*+,-./:;<=>?@[\\]^`{|}~'
# Frames the translator bolts onto the German source, in the order the original
# console script stripped them.
GENDER_MARKERS = (
    "Я девочка",
    "Я - девочка",
    "Я девушка",
    "Я - девушка",
    "Я девчонка",
)
MIN_SENTENCE_CHARS = 25
MAX_SENTENCE_CHARS = 400

_morph = pymorphy3.MorphAnalyzer()
_executor = ThreadPoolExecutor(max_workers=4)
_cache_lock = threading.Lock()
_sentences: list[str] | None = None


# --------------------------------------------------------------------------- #
# The one and only event loop
# --------------------------------------------------------------------------- #
# googletrans builds an httpx AsyncClient that binds itself to whichever loop
# first awaits it, and the connection pool is then useless on any other loop.
# Flask gives every request a fresh thread, so instead of asyncio.run() per
# request we park a single long-lived loop in a daemon thread and submit work
# to it.  The translator is created lazily *inside* that loop, for the same
# reason.
_loop = asyncio.new_event_loop()
_loop_thread: threading.Thread | None = None
_loop_lock = threading.Lock()
_translator: Translator | None = None


def _loop_forever() -> None:
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop_thread
    if _loop_thread is None or not _loop_thread.is_alive():
        with _loop_lock:
            if _loop_thread is None or not _loop_thread.is_alive():
                _loop_thread = threading.Thread(
                    target=_loop_forever, name="annemarie-loop", daemon=True
                )
                _loop_thread.start()
    return _loop


def _get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def run_sync(coro, timeout: float = 60.0):
    """Run a coroutine on the shared loop and return its result (blocking).

    This is the sync entry point Flask's worker threads call.
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=timeout)
    except asyncio.TimeoutError:
        future.cancel()
        raise


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #
def _clean_sentence(raw: str) -> str:
    sentence = raw.replace("\n", " ").replace("\r", " ")
    sentence = re.sub(r"\s+", " ", sentence).strip()
    # The original removed digits one character at a time; strip whole numbers
    # so words like "zweitausendfünfhundert" do not collapse into fragments.
    sentence = re.sub(r"\d[\d.,]*", "", sentence)
    sentence = re.sub(r"\s+([.,;:!?])", r"\1", sentence)
    sentence = re.sub(r"\s{2,}", " ", sentence).strip()
    return sentence


def _parse_pdf() -> list[str]:
    reader = PdfReader(PDF_PATH)
    text = "".join(page.extract_text() or "" for page in reader.pages)
    raw_sentences = re.findall(r"[^.!?]+[.!?]", text)
    corpus = []
    for raw in raw_sentences:
        sentence = _clean_sentence(raw)
        if not (MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS):
            continue
        if not any(ch.isalpha() for ch in sentence):
            continue
        corpus.append(sentence)
    return corpus


def get_sentences() -> list[str]:
    """Return the parsed sentence corpus, loading (and caching) it on demand.

    Blocking: parse ~92 PDF pages on first call, then serve from cache.  Call
    this from ``generate()`` via ``_offload`` so the event loop stays free.
    """
    global _sentences
    if _sentences is not None:
        return _sentences
    with _cache_lock:
        if _sentences is not None:
            return _sentences
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as handle:
                    cached = json.load(handle)
                if isinstance(cached, list) and cached:
                    _sentences = cached
                    return _sentences
            except (OSError, ValueError):
                pass  # cache is corrupt, fall through and re-parse
        parsed = _parse_pdf()
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as handle:
                json.dump(parsed, handle, ensure_ascii=False)
        except OSError:
            pass  # cache is an optimisation, never fatal
        _sentences = parsed
        return _sentences


def corpus_stats() -> dict:
    sentences = get_sentences()
    return {"sentences": len(sentences), "source": os.path.basename(PDF_PATH)}


# --------------------------------------------------------------------------- #
# Async <-> sync plumbing
# -------------------------------------------------------------------------- #
async def translate(text: str, src: str, dest: str) -> str:
    result = await _get_translator().translate(text, src=src, dest=dest)
    return result.text


async def _offload(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, func, *args)


# --------------------------------------------------------------------------- #
# Text processing
# --------------------------------------------------------------------------- #
def censor(text: str) -> str:
    for word, blocks in CENSORED.items():
        if word in text:
            text = text.replace(word, "\u2588" * blocks)
    return text


def _squash_blocks(text: str) -> str:
    """Google translates a run of █ into spaced-out blocks; glue them back."""
    return re.sub(r"\s*\u2588(?:\s*\u2588)+\s*", "\u2588", text)


def remove_with_mark(text: str, phrase: str) -> str:
    if phrase not in text:
        return text
    text = re.sub(rf"\b{re.escape(phrase)}\b[^\w\s]?", "", text, count=1)
    text = text.lstrip()
    if text:
        text = text[0].upper() + text[1:]
    return text


def feminize(text: str) -> str:
    """Switch masculine past-tense verbs to feminine after 'я'."""
    tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
    result: list[str] = []
    awaiting_verb = False

    for token in tokens:
        if token.lower() == "я":
            awaiting_verb = True
            result.append(token)
            continue
        if awaiting_verb:
            parsed = _morph.parse(token)[0]
            if "VERB" in parsed.tag:
                if "masc" in parsed.tag:
                    feminine = parsed.inflect({"femn"})
                    if feminine:
                        token = (
                            feminine.word.capitalize()
                            if token.istitle()
                            else feminine.word
                        )
                awaiting_verb = False
        result.append(token)

    processed = " ".join(result)
    return re.sub(r"\s+([.,!?;:])", r"\1", processed)


def keyword_from(phrase_de: str) -> str:
    words = [w for w in phrase_de.lower().split(" ") if w.strip()]
    if not words:
        return ""
    longest = max(words, key=len)
    return "".join(ch for ch in longest if ch not in PUNCTUATION)


def pick_sentence(sentences: list[str], keyword: str) -> str:
    """Prefer a sentence mentioning the keyword, else any random sentence."""
    if keyword:
        needle = " " + keyword.lower()
        matches = [s for s in sentences if needle in s.lower()]
        if matches:
            return random.choice(matches)
    return random.choice(sentences)


def lower_first(sentence: str) -> str:
    sentence = sentence.lstrip()
    if not sentence:
        return sentence
    return sentence[0].lower() + sentence[1:]


# --------------------------------------------------------------------------- #
# High level generator
# --------------------------------------------------------------------------- #
TRANSLATE_ATTEMPTS = 3


async def _translate_retry(text: str, src: str, dest: str) -> str:
    """Google drops connections; a 1995 dial-up page retried on its own."""
    last_error: Exception | None = None
    for attempt in range(TRANSLATE_ATTEMPTS):
        try:
            return await translate(text, src=src, dest=dest)
        except Exception as exc:  # network flakiness, timeouts, bad gateway
            last_error = exc
            if attempt < TRANSLATE_ATTEMPTS - 1:
                await asyncio.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"Переводчик не отвечает: {last_error}")


async def generate(user_phrase: str) -> dict:
    """Run the full console pipeline for one user phrase."""
    phrase = (user_phrase or "").strip()
    if not phrase:
        raise ValueError("Пустая фраза")

    # First call parses the PDF; keep that off the event loop.
    sentences = await _offload(get_sentences)
    source_de = await _translate_retry(phrase, src="ru", dest="de")
    keyword = keyword_from(source_de)

    if keyword:
        needle = " " + keyword.lower()
        matches = [s for s in sentences if needle in s.lower()]
    else:
        matches = []
    matched = bool(matches)

    first = pick_sentence(sentences, keyword)
    second = random.choice(sentences)
    third = random.choice(sentences)
    while third == second:
        third = random.choice(sentences)

    composed = " ".join(
        [
            lower_first(first).replace(".", ","),
            lower_first(second).replace(".", ","),
            third,
        ]
    )

    # Black out the drugs in the German source, as annemarie_v2.py did in
    # random_sentence().  The █ blocks survive the round trip through Google.
    composed = censor(composed)

    result_ru = await _translate_retry(
        "ich bin ein Mädchen, " + composed, src="de", dest="ru"
    )

    for marker in GENDER_MARKERS:
        result_ru = remove_with_mark(result_ru, marker)
    result_ru = await _offload(feminize, result_ru)
    # Safety net for Russian spellings the translator may have produced, and
    # glue back the spaced-out blocks Google tends to emit.
    result_ru = _squash_blocks(censor(result_ru)).strip()

    return {
        "input": phrase,
        "source_de": source_de,
        "keyword_de": keyword,
        "keyword_matched": matched,
        "match_count": len(matches),
        "text": result_ru,
        "source_sentences": [
            first.strip(),
            second.strip(),
            third.strip(),
        ],
        "composed_de": composed,
    }


def generate_sync(user_phrase: str) -> dict:
    """Blocking entry point for Flask's request threads."""
    return run_sync(generate(user_phrase), timeout=90.0)
