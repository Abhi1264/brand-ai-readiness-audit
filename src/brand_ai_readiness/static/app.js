(() => {
  const RECENT_KEY = "aira.recent";
  const STAGES = [
    "Reaching the site",
    "Reading robots.txt",
    "Comparing AI crawler access",
    "Walking linked pages",
    "Parsing structured data",
    "Checking brand names",
    "Looking for dates",
    "Reviewing the first visit",
  ];

  let stageTimer = 0;
  let elapsedTimer = 0;
  let printBound = false;

  function $(selector, root = document) {
    return root.querySelector(selector);
  }

  function readRecent() {
    try {
      const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(raw) ? raw.filter((item) => (item.host || "").includes(".")) : [];
    } catch {
      return [];
    }
  }

  function writeRecent(url) {
    const host =
      $(".report-host")?.textContent?.trim() ||
      url.replace(/^https?:\/\//, "").replace(/\/$/, "");
    const next = [{ url, host }, ...readRecent().filter((item) => item.url !== url)].slice(0, 5);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  }

  function renderRecent(form) {
    const wrap = $("[data-recent]", form);
    const list = $("[data-recent-list]", wrap || document);
    const input = $("#url", form);
    if (!wrap || !list) return;
    const items = readRecent();
    if (!items.length) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    list.replaceChildren(
      ...items.map((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = item.host;
        button.addEventListener("click", () => {
          if (!input) return;
          input.value = item.url;
          input.focus();
        });
        return button;
      }),
    );
  }

  function stopChecking() {
    window.clearInterval(stageTimer);
    window.clearInterval(elapsedTimer);
    stageTimer = 0;
    elapsedTimer = 0;
  }

  function startChecking(form) {
    const checking = $("[data-checking]");
    const stage = $("[data-stage]", checking);
    const urlLabel = $("[data-checking-url]", checking);
    const elapsed = $("[data-elapsed]", checking);
    const url = $("#url", form);

    document.body.classList.add("is-checking");
    document.body.setAttribute("aria-busy", "true");
    if (checking) {
      checking.hidden = false;
      checking.removeAttribute("inert");
    }
    if (urlLabel && url) urlLabel.textContent = url.value.trim();

    let index = 0;
    const started = Date.now();
    if (stage) stage.textContent = STAGES[0];
    stopChecking();
    stageTimer = window.setInterval(() => {
      index = (index + 1) % STAGES.length;
      if (stage) stage.textContent = STAGES[index];
    }, 2200);
    elapsedTimer = window.setInterval(() => {
      const seconds = Math.max(1, Math.round((Date.now() - started) / 1000));
      if (elapsed) elapsed.textContent = `${seconds}s elapsed · usually under a minute`;
    }, 1000);
  }

  async function swapDocument(html) {
    const next = new DOMParser().parseFromString(html, "text/html");
    const fresh = next.body;
    if (!fresh) throw new Error("empty-response");
    stopChecking();
    document.title = next.title || document.title;
    document.body.replaceWith(fresh);
    boot();
    const verdict = document.getElementById("verdict-title");
    if (verdict) {
      verdict.focus({ preventScroll: true });
      verdict.scrollIntoView({ block: "start" });
    }
  }

  function bindForm() {
    const form = $("[data-audit-form]");
    if (!form || form.dataset.bound === "true") return;
    form.dataset.bound = "true";
    const range = $("[data-pages-range]", form);
    const out = $("[data-pages-out]", form);
    if (range && out) {
      const sync = () => {
        out.value = range.value;
      };
      range.addEventListener("input", sync);
      sync();
    }
    renderRecent(form);

    const firstError = $("[data-field-error]", form);
    const url = $("#url", form);
    if (firstError && url) url.focus();

    form.addEventListener("submit", async (event) => {
      const urlValue = ($("#url", form)?.value || "").trim();
      if (!urlValue) return;
      event.preventDefault();
      startChecking(form);
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { Accept: "text/html" },
        });
        const html = await response.text();
        await swapDocument(html);
        if (document.querySelector("[data-results]")) writeRecent(urlValue);
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("url", urlValue);
        history.replaceState({}, "", `${nextUrl.pathname}${nextUrl.search}`);
      } catch {
        stopChecking();
        form.submit();
      }
    });
  }

  function bindDownload() {
    const download = $("[data-download]");
    const payload = document.getElementById("report-json");
    if (!download || !payload) return;
    download.addEventListener("click", (event) => {
      event.preventDefault();
      const blob = new Blob([payload.textContent || "{}"], { type: "application/json" });
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const site = download.getAttribute("data-site") || "site";
      link.href = href;
      link.download = `${site}-site-check.json`;
      link.click();
      URL.revokeObjectURL(href);
    });
  }

  function bindCopyLink() {
    const button = $("[data-copy-link]");
    if (!button || !navigator.clipboard) return;
    button.addEventListener("click", async () => {
      const urlInput = $("#url");
      const target = new URL(window.location.origin + "/");
      if (urlInput?.value) target.searchParams.set("url", urlInput.value.trim());
      await navigator.clipboard.writeText(target.toString());
      button.textContent = "Link copied";
      window.setTimeout(() => {
        button.textContent = "Copy check link";
      }, 1600);
    });
  }

  function bindFindingCopies() {
    document.querySelectorAll("[data-copy-finding]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (!navigator.clipboard) return;
        const article = button.closest("[data-finding]");
        if (!article) return;
        const text = [
          article.querySelector("h3")?.textContent?.trim(),
          article.querySelector(".finding-fix")?.textContent?.trim(),
          article.querySelector(".evidence")?.textContent?.trim(),
        ]
          .filter(Boolean)
          .join("\n\n");
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied";
        window.setTimeout(() => {
          button.textContent = "Copy this issue";
        }, 1400);
      });
    });
  }

  function bindExpand() {
    const findings = document.querySelectorAll("[data-finding] details");
    $("[data-expand-all]")?.addEventListener("click", () => {
      findings.forEach((item) => {
        item.open = true;
      });
    });
    $("[data-collapse-all]")?.addEventListener("click", () => {
      findings.forEach((item) => {
        item.open = false;
      });
    });
    if (printBound) return;
    printBound = true;
    window.addEventListener("beforeprint", () => {
      document.querySelectorAll("[data-finding] details").forEach((item) => {
        item.open = true;
      });
    });
  }

  function bindFilters() {
    const root = $("[data-filters]");
    if (!root) return;
    const cards = [...document.querySelectorAll("[data-finding]")];
    const empty = $("[data-filter-empty]");
    const status = $("[data-filter-status]");
    let severity = "all";
    let category = "all";

    function paint(group, value) {
      const attr = group === "severity" ? "data-filter-severity" : "data-filter-category";
      root.querySelectorAll(`[${attr}]`).forEach((chip) => {
        const on = chip.getAttribute(attr) === value;
        chip.classList.toggle("is-on", on);
        chip.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }

    function apply() {
      let shown = 0;
      cards.forEach((card) => {
        const match =
          (severity === "all" || card.dataset.severity === severity) &&
          (category === "all" || card.dataset.category === category);
        card.hidden = !match;
        if (match) shown += 1;
      });
      if (empty) empty.hidden = shown !== 0;
      if (status) {
        status.textContent =
          shown === cards.length ? "" : `Showing ${shown} of ${cards.length} issues`;
      }
    }

    root.querySelectorAll("[data-filter-severity]").forEach((chip) => {
      chip.addEventListener("click", () => {
        severity = chip.getAttribute("data-filter-severity") || "all";
        paint("severity", severity);
        apply();
      });
    });
    root.querySelectorAll("[data-filter-category]").forEach((chip) => {
      chip.addEventListener("click", () => {
        category = chip.getAttribute("data-filter-category") || "all";
        paint("category", category);
        apply();
      });
    });
  }

  function paintPcts() {
    document.querySelectorAll("[data-pct]").forEach((el) => {
      el.style.width = `${el.getAttribute("data-pct") || 0}%`;
    });
  }

  function boot() {
    paintPcts();
    bindForm();
    bindDownload();
    bindCopyLink();
    bindFindingCopies();
    bindExpand();
    bindFilters();
  }

  boot();
})();
