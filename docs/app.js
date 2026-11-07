// Klippings product page: the live app preview, the feature demos and the latest release download links
(function () {
  "use strict";

  const REPO = "TariqMK/Klippings";
  const ASSET = { windows: /windows-x64\.exe$/i, macos: /macos-arm64\.zip$/i, linux: /linux-x64\.tar\.gz$/i };
  const OS_NAMES = { windows: "Windows", macos: "macOS", linux: "Linux" };
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.documentElement.classList.add("js");

  // Public-domain books, shown as the app shows them
  const BOOKS = [
    { title: "Walden", author: "Henry David Thoreau", highlights: [
      ["I went to the woods because I wished to live deliberately, to front only the essential facts of life, and see if I could not learn what it had to teach, and not, when I came to die, discover that I had not lived.", 12, "171-173"],
      ["The mass of men lead lives of quiet desperation.", 8, "104-104"],
      ["Our life is frittered away by detail. Simplify, simplify.", 14, "190-191"],
      ["Rather than love, than money, than fame, give me truth.", 52, "702-702"]] },
    { title: "Pride and Prejudice", author: "Jane Austen", highlights: [
      ["It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.", 1, "5-6"],
      ["I declare after all there is no enjoyment like reading!", 47, "702-703"]] },
    { title: "Moby-Dick", author: "Herman Melville", highlights: [
      ["Call me Ishmael.", 1, "3-3"],
      ["It is not down on any map; true places never are.", 52, "905-905"]] },
    { title: "Frankenstein", author: "Mary Shelley", highlights: [
      ["Beware; for I am fearless, and therefore powerful.", 158, "2511-2511"],
      ["Nothing is so painful to the human mind as a great and sudden change.", 70, "1120-1121"]] },
    { title: "Jane Eyre", author: "Charlotte Bronte", highlights: [
      ["I am no bird; and no net ensnares me: I am a free human being with an independent will.", 255, "4102-4103"],
      ["Reader, I married him.", 498, "8010-8010"]] },
    { title: "A Tale of Two Cities", author: "Charles Dickens", highlights: [
      ["It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness.", 1, "2-4"]] }
  ];

  const $ = (id) => document.getElementById(id);
  const escape = (text) => text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const place = (page, location) => {
    const [start, end] = location.split("-");
    return `Page ${page} · Location ${start === end || !end ? start : location}`;
  };

  // ---- App preview ----
  const included = BOOKS.map(() => true);
  let selected = 0;
  let touched = false;
  const list = $("book-list");
  const reading = $("reading");
  const maxCount = Math.max(...BOOKS.map((b) => b.highlights.length));

  function renderBooks() {
    list.innerHTML = BOOKS.map((book, i) => `
      <li class="book${i === selected ? " selected" : ""}${included[i] ? "" : " off"}" data-i="${i}">
        <span class="box" data-toggle="${i}" role="checkbox" aria-checked="${included[i]}" aria-label="Include ${escape(book.title)}"></span>
        <span class="book-title">${escape(book.title)}</span>
        <span class="book-count">${book.highlights.length}</span>
        <span class="book-bar" style="width:${Math.round((book.highlights.length / maxCount) * 100)}%"></span>
      </li>`).join("");
  }

  function renderReading() {
    const book = BOOKS[selected];
    reading.innerHTML = `<h3 class="r-title">${escape(book.title)}</h3><p class="r-author">${escape(book.author)}</p>` +
      book.highlights.map(([text, page, loc]) =>
        `<p class="r-hl"><span>${escape(text)}</span></p><p class="r-place">${place(page, loc)}</p>`).join("");
  }

  function renderExport() {
    const text = $("opt-text").checked;
    const images = $("opt-images").checked;
    $("opt-meta-row").hidden = !text;
    $("font-pick").hidden = !images;
    reading.classList.toggle("no-meta", text && !$("opt-meta").checked);
    const count = included.filter(Boolean).length;
    const button = $("export-button");
    let label = `Export ${count} ${count === 1 ? "Book" : "Books"}`;
    if (!count) label = "Export";
    else if (!text && !images) label = "Choose What to Export";
    button.textContent = label;
    button.classList.toggle("disabled", !count || (!text && !images));
    $("book-summary").textContent = `${BOOKS.length} books, ${BOOKS.reduce((n, b) => n + b.highlights.length, 0)} highlights`;
  }

  list.addEventListener("click", (event) => {
    const row = event.target.closest(".book");
    if (!row) return;
    touched = true;
    const i = Number(row.dataset.i);
    if (event.target.closest("[data-toggle]")) included[i] = !included[i];
    else selected = i;
    renderBooks();
    renderReading();
    renderExport();
  });
  ["opt-text", "opt-meta", "opt-images"].forEach((id) => $(id).addEventListener("change", () => { touched = true; renderExport(); }));

  renderBooks();
  renderReading();
  renderExport();

  // Move through the books until the visitor takes over
  if (!reduceMotion) {
    setInterval(() => {
      if (touched || document.hidden) return;
      selected = (selected + 1) % BOOKS.length;
      renderBooks();
      renderReading();
    }, 4000);
  }

  // ---- Text file demo, in the exporter's exact format ----
  function renderFile() {
    const book = BOOKS[0];
    const withMeta = $("demo-meta").checked;
    $("file-name").textContent = withMeta ? `${book.title}.txt` : `${book.title} (simple).txt`;
    let body;
    if (withMeta) {
      body = book.highlights.map(([text, page, loc], i) =>
        `${i + 1}. ${escape(text)}\n\t<span class="dim">&lt;${escape(book.title)}&gt;(${escape(book.author)}) Your Highlight on page ${page} | location ${loc}</span>\n`).join("\n");
    } else {
      body = `${escape(book.title)}\n${escape(book.author)}\n\n<span class="dim">---</span>\n\n` +
        book.highlights.map(([text], i) => `${i + 1}. ${escape(text)}`).join(`\n\n<span class="dim">---</span>\n\n`);
    }
    $("file-body").innerHTML = body;
  }
  $("demo-meta").addEventListener("change", renderFile);
  renderFile();

  // ---- Quote image demo ----
  const QUOTES = [
    { book: 0, text: "I went to the woods because I wished to live deliberately, to front only the essential facts of life, and see if I could not learn what it had to teach, and not, when I came to die, discover that I had not lived.", part: 1, total: 1, file: "Walden/Highlight_0001.webp" },
    { book: 1, text: "I declare after all there is no enjoyment like reading!", part: 1, total: 1, file: "Pride and Prejudice/Highlight_0002.webp" },
    { book: 3, text: "Nothing is so painful to the human mind as a great and sudden change.", part: 1, total: 1, file: "Frankenstein/Highlight_0002.webp" },
    { book: 4, text: "I am no bird; and no net ensnares me: I am a free human being with an independent will.", part: 1, total: 1, file: "Jane Eyre/Highlight_0001.webp" }
  ];
  let quote = 0;
  function renderQuote() {
    const q = QUOTES[quote];
    const book = BOOKS[q.book];
    $("quote-text").textContent = q.text;
    $("quote-by").textContent = `${book.title} | ${book.author}`;
    $("quote-ticks").innerHTML = q.total > 1 ? Array.from({ length: q.total }, (_, i) => `<i class="${i + 1 === q.part ? "on" : ""}"></i>`).join("") : "";
    $("quote-file").textContent = q.file;
  }
  $("quote-prev").addEventListener("click", () => { quote = (quote + QUOTES.length - 1) % QUOTES.length; renderQuote(); });
  $("quote-next").addEventListener("click", () => { quote = (quote + 1) % QUOTES.length; renderQuote(); });
  renderQuote();

  // ---- Signature highlight: sweep in when it comes into view ----
  const marks = document.querySelectorAll(".sel");
  if ("IntersectionObserver" in window && !reduceMotion) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add("on"); observer.unobserve(entry.target); }
      });
    }, { threshold: 0.6 });
    marks.forEach((mark) => observer.observe(mark));
  } else {
    marks.forEach((mark) => mark.classList.add("on"));
  }
  requestAnimationFrame(() => document.body.classList.add("loaded"));

  // ---- Downloads ----
  function detectOS() {
    const ua = navigator.userAgent;
    if (/Android|iPhone|iPad|iPod/i.test(ua)) return null;
    if (/Windows/i.test(ua)) return "windows";
    if (/Mac/i.test(ua)) return "macos";
    if (/Linux|X11/i.test(ua)) return "linux";
    return null;
  }
  const os = detectOS();
  const heroButton = $("hero-download");
  if (os) {
    heroButton.textContent = `Download for ${OS_NAMES[os]}`;
    const card = document.querySelector(`.card[data-os="${os}"]`);
    if (card) card.classList.add("mine");
  }

  fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
    .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
    .then((release) => {
      for (const asset of release.assets || []) {
        for (const [key, pattern] of Object.entries(ASSET)) {
          if (!pattern.test(asset.name)) continue;
          const card = document.querySelector(`.card[data-os="${key}"]`);
          if (card) {
            card.href = asset.browser_download_url;
            card.querySelector(".card-size").textContent = `· ${(asset.size / 1048576).toFixed(1)} MB`;
          }
          if (key === os) heroButton.href = asset.browser_download_url;
        }
      }
      const date = new Date(release.published_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
      $("download-version").textContent = `${release.tag_name} · ${date}`;
      $("hero-meta").textContent = `${release.tag_name} · Free · Windows, macOS and Linux`;
    })
    .catch(() => {});
})();
