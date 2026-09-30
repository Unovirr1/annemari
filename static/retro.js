/* ============================================================
   СЧАСТЛИВАЯ ДОЛИНА — client script
   Talks to /api/generate, then renders the result like 1995 would.
   No frameworks. Uses fetch + async/await, which is fine: the *look* is
   1995, the engine is not.
   ============================================================ */
(function () {
  "use strict";

  var outEl     = document.getElementById("out");
  var statusEl  = document.getElementById("status");
  var metaEl    = document.getElementById("outmeta");
  var phraseEl  = document.getElementById("phrase");
  var goEl      = document.getElementById("go");
  var speakEl   = document.getElementById("speakBtn");
  var counterEl = document.getElementById("counter");

  // ------------------------------------------------------------------ //
  // Tiled background (set from JS so a missing image leaves flat navy)
  // ------------------------------------------------------------------ //
  var bg = new Image();
  bg.onload = function () {
    document.body.style.backgroundImage = "url('" + bg.src + "')";
    document.body.style.backgroundRepeat = "repeat";
  };
  bg.src = "/static/space.png";

  // ------------------------------------------------------------------ //
  // Hit counter animation: roll up to the real number like a CGI script
  // ------------------------------------------------------------------ //
  (function rollCounter() {
    if (!counterEl) { return; }
    var target = parseInt(counterEl.textContent.replace(/\D/g, ""), 10);
    if (isNaN(target) || target <= 1) { return; }

    var start = Math.max(0, target - 40);
    var tick = 0;
    var timer = setInterval(function () {
      tick += 4;
      var value = Math.min(target, start + tick);
      counterEl.textContent = ("000000" + value).slice(-6);
      if (value >= target) { clearInterval(timer); }
    }, 40);
  })();

  // ------------------------------------------------------------------ //
  // Status line
  // ------------------------------------------------------------------ //
  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.className = isError ? "err" : "";
  }

  // ------------------------------------------------------------------ //
  // Render: type the text out one character at a time
  // ------------------------------------------------------------------ //
  var typingTimer = null;

  function renderText(text) {
    if (typingTimer) { clearInterval(typingTimer); }

    outEl.textContent = "";
    var i = 0;
    var chunk = Math.max(1, Math.round(text.length / 90));

    typingTimer = setInterval(function () {
      i = Math.min(text.length, i + chunk);
      outEl.textContent = text.slice(0, i);
      if (i >= text.length) {
        clearInterval(typingTimer);
        typingTimer = null;
        // Now that the full text is in, wrap the censor blocks in colour.
        paintOutput(text);
      }
    }, 22);
  }

  /* The book censors Hashish/Opium with █ blocks; wrap them so they read
     as deliberate redactions rather than font failures. */
  function paintOutput(text) {
    outEl.textContent = "";
    var parts = text.split(/(\u2588+)/);
    parts.forEach(function (part) {
      if (/^\u2588+$/.test(part)) {
        var span = document.createElement("span");
        span.className = "blocked";
        span.textContent = part;
        outEl.appendChild(span);
      } else {
        outEl.appendChild(document.createTextNode(part));
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Main request
  // ------------------------------------------------------------------ //
  function generate() {
    var phrase = phraseEl.value.replace(/^\s+|\s+$/g, "");
    if (!phrase) {
      setStatus("Пустая фраза! Напишите хоть что-нибудь.", true);
      return;
    }

    goEl.disabled = true;
    setStatus("Соединение с переводчиком... подождите, это же 1995-й.");

    fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phrase: phrase })
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) { throw new Error(data.error || "Ошибка сервера"); }
          return data;
        });
      })
      .then(function (data) {
        renderText(data.text);
        speakText = data.text;

        var meta = "источник: " + data.source_de + "  ·  ключевое слово: ";
        meta += data.keyword_de
          ? data.keyword_de + (data.keyword_matched
              ? " (найдено предложений: " + data.match_count + ")"
              : " (в книге не найдено)")
          : "—";
        metaEl.textContent = meta;

        setStatus(data.keyword_matched
          ? "Готово! Нажмите «ПРОЧИТАТЬ», чтобы услышать."
          : "Готово, но ключевое слово в книге не встретилось.");
      })
      .catch(function (err) {
        setStatus("Ошибка: " + err.message, true);
        outEl.textContent = "";
      })
      .finally(function () {
        goEl.disabled = false;
      });
  }

  // ------------------------------------------------------------------ //
  // Speech: Web Speech API, Russian voice if the OS has one
  // ------------------------------------------------------------------ //
  var speakText = "";

  function pickRussianVoice() {
    var voices = window.speechSynthesis.getVoices() || [];
    for (var i = 0; i < voices.length; i++) {
      if (/ru[-_]?/i.test(voices[i].lang)) { return voices[i]; }
    }
    return null;
  }

  function speakCurrent() {
    var text = speakText || outEl.textContent;
    if (!text.trim()) {
      setStatus("Сначала создайте текст, потом читайте его вслух.", true);
      return;
    }
    if (!("speechSynthesis" in window)) {
      setStatus("Ваш браузер не умеет читать вслух. Это 1995 год.", true);
      return;
    }

    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(text);
    var voice = pickRussianVoice();
    if (voice) { utterance.voice = voice; }
    utterance.lang = voice ? voice.lang : "ru-RU";
    utterance.rate = 0.95;
    utterance.pitch = 1.1;

    utterance.onstart = function () { setStatus("Читаю вслух..."); };
    utterance.onend = function () { setStatus("Готово! Что ещё сгенерируем?"); };
    utterance.onerror = function () { setStatus("Голос не сработал. Попробуйте снова.", true); };

    window.speechSynthesis.speak(utterance);
  }

  // Some browsers populate getVoices() only after the event fires.
  if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = function () { pickRussianVoice(); };
  }

  // ------------------------------------------------------------------ //
  // Random Russian phrase, for people who cannot think of one
  // ------------------------------------------------------------------ //
  var PHRASES = [
    "я иду в горы и там нахожу снег",
    "я хочу увидеть настоящее счастливое озеро",
    "мы ночуем в палатке у самой реки",
    "я боюсь темноты в горах",
    "там внизу видно облака и людей",
    "я несу рюкзак через перевал",
    "мне снятся белые вершины и тишина",
    "я потерялась среди камней и ветра",
    "мы едем верхом по горной дороге",
    "я пишу письмо домой из долины"
  ];

  function randomPhrase() {
    var current = phraseEl.value;
    var pick = current;
    while (pick === current) {
      pick = PHRASES[Math.floor(Math.random() * PHRASES.length)];
    }
    phraseEl.value = pick;
  }

  // ------------------------------------------------------------------ //
  // Wire up
  // ------------------------------------------------------------------ //
  window.generate = generate;
  window.speakCurrent = speakCurrent;
  window.randomPhrase = randomPhrase;
})();
