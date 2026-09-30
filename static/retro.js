/* ============================================================
   СЧАСТЛИВАЯ ДОЛИНА — client script
   Talks to /api/generate, then renders the result like 1995 would.
   No frameworks. Uses fetch + async/await, which is fine: the *look* is
   1995, the engine is not.
   Dialogue window: after first «СОЗДАТЬ ТЕКСТ» the home sections
   (generator/about/howto/links) hide and a chat log with its own
   input is shown. History persists in localStorage.
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

  var rowGenerator = document.getElementById("row-generator");
  var rowDialogue  = document.getElementById("row-dialogue");
  var rowAbout     = document.getElementById("row-about");
  var rowHowto     = document.getElementById("row-howto");
  var rowLinks     = document.getElementById("row-links");
  var homeSpacers  = document.querySelectorAll(".spacer-home");
  var chatlogEl    = document.getElementById("chatlog");
  var chatPhraseEl = document.getElementById("chatPhrase");
  var chatGoEl     = document.getElementById("chatGo");
  var chatStatusEl = document.getElementById("chatStatus");
  var chatCountEl  = document.getElementById("chatCount");
  var resumeWrapEl = document.getElementById("resumeWrap");
  var resumeLinkEl = document.getElementById("resumeLink");
  var navDialogEl  = document.getElementById("navDialog");

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
  // Status line (mirrored into the chat status so both views stay in sync)
  // ------------------------------------------------------------------ //
  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.className = isError ? "err" : "";
    if (chatStatusEl) {
      chatStatusEl.textContent = text;
      chatStatusEl.className = isError ? "err" : "";
    }
  }

  function setChatStatus(text, isError) {
    if (chatStatusEl) {
      chatStatusEl.textContent = text;
      chatStatusEl.className = isError ? "err" : "";
    }
  }

  // ------------------------------------------------------------------ //
  // Dialogue history (localStorage, survives reload)
  // ------------------------------------------------------------------ //
  var LS_KEY = "dolina_dialog_v1";
  var MAX_HISTORY = 100;
  var history = loadHistory();

  function loadHistory() {
    try {
      var raw = window.localStorage.getItem(LS_KEY);
      if (!raw) { return []; }
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveHistory() {
    try {
      window.localStorage.setItem(LS_KEY, JSON.stringify(history));
    } catch (e) { /* private mode etc. — history just stays in memory */ }
    updateCounts();
  }

  function updateCounts() {
    if (chatCountEl) { chatCountEl.textContent = String(history.length); }
    if (resumeWrapEl && resumeLinkEl) {
      if (history.length > 0) {
        resumeWrapEl.style.display = "";
        resumeLinkEl.textContent = "Продолжить диалог (" + history.length + ") →";
      } else {
        resumeWrapEl.style.display = "none";
      }
    }
  }

  // ------------------------------------------------------------------ //
  // View switching: home sections <-> chat-only dialogue
  // ------------------------------------------------------------------ //
  function setRowVisible(row, visible) {
    if (!row) { return; }
    row.style.display = visible ? "" : "none";
  }

  function showDialogue() {
    setRowVisible(rowGenerator, false);
    setRowVisible(rowAbout, false);
    setRowVisible(rowHowto, false);
    setRowVisible(rowLinks, false);
    for (var i = 0; i < homeSpacers.length; i++) {
      homeSpacers[i].style.display = "none";
    }
    setRowVisible(rowDialogue, true);
    scrollChatToBottom();
  }

  function showHome() {
    setRowVisible(rowGenerator, true);
    setRowVisible(rowAbout, true);
    setRowVisible(rowHowto, true);
    setRowVisible(rowLinks, true);
    for (var j = 0; j < homeSpacers.length; j++) {
      homeSpacers[j].style.display = "";
    }
    setRowVisible(rowDialogue, false);
  }

  function isDialogueVisible() {
    return !!(rowDialogue && rowDialogue.style.display !== "none");
  }

  // ------------------------------------------------------------------ //
  // Render: type the text out one character at a time (legacy panel)
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
    paintBlocksInto(outEl, text);
  }

  function paintBlocksInto(node, text) {
    node.textContent = "";
    var parts = String(text).split(/(\u2588+)/);
    parts.forEach(function (part) {
      if (/^\u2588+$/.test(part)) {
        var span = document.createElement("span");
        span.className = "blocked";
        span.textContent = part;
        node.appendChild(span);
      } else {
        node.appendChild(document.createTextNode(part));
      }
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function metaText(data) {
    var meta = "источник: " + data.source_de + "  ·  ключевое слово: ";
    meta += data.keyword_de
      ? data.keyword_de + (data.keyword_matched
          ? " (найдено предложений: " + data.match_count + ")"
          : " (в книге не найдено)")
      : "—";
    return meta;
  }

  // ------------------------------------------------------------------ //
  // Chat log rendering
  // ------------------------------------------------------------------ //
  function scrollChatToBottom() {
    if (chatlogEl) { chatlogEl.scrollTop = chatlogEl.scrollHeight; }
  }

  function clearChatlogNode() {
    while (chatlogEl.firstChild) { chatlogEl.removeChild(chatlogEl.firstChild); }
  }

  function appendUserNode(phrase) {
    var div = document.createElement("div");
    div.className = "msg-user";
    div.textContent = "ВЫ: " + phrase;
    chatlogEl.appendChild(div);
    scrollChatToBottom();
    return div;
  }

  function appendBotNode(entry, index) {
    var bot = document.createElement("div");
    bot.className = "msg-bot";
    paintBlocksInto(bot, entry.text);
    chatlogEl.appendChild(bot);

    var meta = document.createElement("div");
    meta.className = "msg-meta";
    var time = "";
    if (entry.ts) {
      try { time = new Date(entry.ts).toLocaleString("ru-RU") + " · "; }
      catch (e) { time = ""; }
    }
    meta.innerHTML = escapeHtml(time + metaText(entry)) +
      ' · <a href="#" data-speak="' + index + '">🔊</a>';
    chatlogEl.appendChild(meta);
    scrollChatToBottom();
    return bot;
  }

  function renderHistory() {
    if (!chatlogEl) { return; }
    clearChatlogNode();
    if (!history.length) {
      var empty = document.createElement("font");
      empty.setAttribute("face", "Times New Roman");
      empty.setAttribute("size", "3");
      empty.setAttribute("color", "#666666");
      empty.id = "chatEmpty";
      empty.textContent = "Пока пусто. Напишите фразу внизу — долина ответит.";
      chatlogEl.appendChild(empty);
    } else {
      for (var i = 0; i < history.length; i++) {
        appendUserNode(history[i].phrase);
        appendBotNode(history[i], i);
      }
    }
    updateCounts();
    scrollChatToBottom();
  }

  // Per-message speaker (event delegation, survives re-render).
  if (chatlogEl) {
    chatlogEl.addEventListener("click", function (ev) {
      var t = ev.target;
      if (t && t.getAttribute && t.getAttribute("data-speak") !== null) {
        ev.preventDefault();
        var idx = parseInt(t.getAttribute("data-speak"), 10);
        if (!isNaN(idx) && history[idx]) { speakTextString(history[idx].text); }
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Main request (shared by both inputs)
  // ------------------------------------------------------------------ //
  var busy = false;

  function submitPhrase(phrase) {
    phrase = (phrase || "").replace(/^\s+|\s+$/g, "");
    if (!phrase) {
      setStatus("Пустая фраза! Напишите хоть что-нибудь.", true);
      return;
    }
    if (busy) { return; }
    busy = true;
    if (goEl) { goEl.disabled = true; }
    if (chatGoEl) { chatGoEl.disabled = true; }
    showDialogue();
    setStatus("Соединение с переводчиком... подождите, это же 1995-й.");

    // Remove the "empty" placeholder on first message.
    var placeholder = document.getElementById("chatEmpty");
    if (placeholder) { placeholder.parentNode.removeChild(placeholder); }

    appendUserNode(phrase);
    var pending = document.createElement("div");
    pending.className = "msg-pending";
    pending.textContent = "Долина думает... ▌";
    chatlogEl.appendChild(pending);
    scrollChatToBottom();

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
        // Legacy panel mirror (kept for the E2E probe + old bookmarks).
        renderText(data.text);
        speakText = data.text;
        metaEl.textContent = metaText(data);

        var entry = {
          phrase: phrase,
          text: data.text,
          source_de: data.source_de,
          keyword_de: data.keyword_de,
          keyword_matched: data.keyword_matched,
          match_count: data.match_count,
          ts: Date.now()
        };
        history.push(entry);
        if (history.length > MAX_HISTORY) {
          history = history.slice(history.length - MAX_HISTORY);
        }
        saveHistory();

        if (pending.parentNode) { pending.parentNode.removeChild(pending); }
        typeBotNode(entry, history.length - 1);

        setStatus(data.keyword_matched
          ? "Готово! Нажмите «ПРОЧИТАТЬ», чтобы услышать."
          : "Готово, но ключевое слово в книге не встретилось.");
      })
      .catch(function (err) {
        if (pending.parentNode) { pending.parentNode.removeChild(pending); }
        var fail = document.createElement("div");
        fail.className = "msg-pending";
        fail.textContent = "Ошибка: " + err.message;
        chatlogEl.appendChild(fail);
        scrollChatToBottom();
        setStatus("Ошибка: " + err.message, true);
        outEl.textContent = "";
      })
      .finally(function () {
        busy = false;
        if (goEl) { goEl.disabled = false; }
        if (chatGoEl) { chatGoEl.disabled = false; }
      });
  }

  // Typewriter for the newest bot reply, then paint censor blocks + meta.
  var chatTypingTimer = null;
  function typeBotNode(entry, index) {
    var bot = document.createElement("div");
    bot.className = "msg-bot";
    chatlogEl.appendChild(bot);
    if (chatTypingTimer) { clearInterval(chatTypingTimer); }
    var text = entry.text;
    var i = 0;
    var chunk = Math.max(1, Math.round(text.length / 90));
    chatTypingTimer = setInterval(function () {
      i = Math.min(text.length, i + chunk);
      bot.textContent = text.slice(0, i);
      scrollChatToBottom();
      if (i >= text.length) {
        clearInterval(chatTypingTimer);
        chatTypingTimer = null;
        paintBlocksInto(bot, text);
        var meta = document.createElement("div");
        meta.className = "msg-meta";
        var time = "";
        try { time = new Date(entry.ts).toLocaleString("ru-RU") + " · "; }
        catch (e) { time = ""; }
        meta.innerHTML = escapeHtml(time + metaText(entry)) +
          ' · <a href="#" data-speak="' + index + '">🔊</a>';
        chatlogEl.appendChild(meta);
        scrollChatToBottom();
      }
    }, 22);
  }

  function generate() {
    submitPhrase(phraseEl.value);
  }

  function chatSend() {
    var phrase = chatPhraseEl ? chatPhraseEl.value : "";
    submitPhrase(phrase);
    if (chatPhraseEl) { chatPhraseEl.value = ""; }
    if (phraseEl && chatPhraseEl) {
      // Keep the legacy input in sync for anyone still using it.
      phraseEl.value = phrase;
    }
  }

  function clearDialogue() {
    history = [];
    saveHistory();
    renderHistory();
    setChatStatus("Диалог стёрт. Долина всё забыла.");
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

  function speakTextString(text) {
    if (!text || !text.trim()) {
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

  function speakCurrent() {
    var text = speakText;
    if (!text && history.length) { text = history[history.length - 1].text; }
    if (!text) { text = outEl.textContent; }
    speakTextString(text);
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

  function chatRandom() {
    if (!chatPhraseEl) { randomPhrase(); return; }
    var current = chatPhraseEl.value || phraseEl.value;
    var pick = current;
    while (pick === current) {
      pick = PHRASES[Math.floor(Math.random() * PHRASES.length)];
    }
    chatPhraseEl.value = pick;
    chatPhraseEl.focus();
  }

  // ------------------------------------------------------------------ //
  // Wire up
  // ------------------------------------------------------------------ //
  if (navDialogEl) {
    navDialogEl.addEventListener("click", function (ev) {
      ev.preventDefault();
      showDialogue();
      if (window.location.hash !== "#dialogue") {
        window.location.hash = "#dialogue";
      }
    });
  }
  if (chatPhraseEl) {
    chatPhraseEl.addEventListener("keydown", function (ev) {
      if (ev.keyCode === 13) { chatSend(); }
    });
  }

  renderHistory();
  if (window.location.hash === "#dialogue" && history.length) {
    showDialogue();
  }

  window.generate = generate;
  window.chatSend = chatSend;
  window.chatRandom = chatRandom;
  window.clearDialogue = clearDialogue;
  window.showDialogue = showDialogue;
  window.showHome = showHome;
  window.isDialogueVisible = isDialogueVisible;
  window.speakCurrent = speakCurrent;
  window.randomPhrase = randomPhrase;
})();
