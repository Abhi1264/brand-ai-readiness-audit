(() => {
  const form = document.querySelector("[data-audit-form]");
  if (!form) return;

  const button = form.querySelector("[data-submit]");
  const status = form.querySelector("[data-status]");
  const url = form.querySelector("#url");
  const firstError = form.querySelector("[data-field-error]");

  if (firstError && url) {
    url.focus();
  }

  form.addEventListener("submit", () => {
    form.classList.add("is-checking");
    if (button) {
      button.disabled = true;
      button.innerHTML =
        '<span class="spinner" aria-hidden="true"></span><span>Checking…</span>';
    }
    if (status) {
      status.hidden = false;
      status.textContent = "This usually takes under a minute…";
    }
  });

  const download = document.querySelector("[data-download]");
  const payload = document.getElementById("report-json");
  if (download && payload) {
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
})();
