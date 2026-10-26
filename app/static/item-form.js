/* Progressive enhancement: native file selection and form submission still work. */
document.querySelectorAll(".item-form").forEach((form) => {
  const picker = form.querySelector("[data-photo-picker]");
  if (!picker) return;
  const input = picker.querySelector("[name=image_file]");
  const link = picker.querySelector("[name=image_url]");
  const remove = picker.querySelector("[name=remove_image]");
  const dropzone = picker.querySelector("[data-photo-dropzone]");
  const preview = picker.querySelector("[data-photo-preview]");
  const empty = picker.querySelector("[data-photo-empty]");
  const message = picker.querySelector("[data-photo-message]");
  const reset = picker.querySelector("[data-photo-reset]");
  const currentUrl = picker.dataset.currentUrl;
  const originalLink = link.value;
  let objectUrl = null;
  let invalidPhoto = false;

  picker.querySelector("[data-photo-drag-hint]").hidden = false;
  const showMessage = (text, error = false) => {
    message.textContent = text;
    message.classList.toggle("is-error", error);
    input.setAttribute("aria-invalid", String(error));
  };
  const render = () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    const file = input.files[0];
    let source = "";
    if (file) {
      objectUrl = URL.createObjectURL(file);
      source = objectUrl;
    } else if (!remove?.checked) {
      source = link.value.trim() || currentUrl;
    }
    preview.hidden = !source;
    empty.hidden = !!source;
    if (source) preview.src = source;
    else preview.removeAttribute("src");
    reset.hidden = !invalidPhoto && !file && !remove?.checked && link.value === originalLink;
  };
  const selected = () => {
    invalidPhoto = false;
    const file = input.files[0];
    if (file && (!/\.(jpe?g|png|webp)$/i.test(file.name) || file.size > 5 * 1024 * 1024 || !file.size)) {
      input.value = "";
      invalidPhoto = true;
      showMessage("Choose one JPG, PNG, or WebP photo up to 5 MB.", true);
    } else if (file) {
      if (remove) remove.checked = false;
      link.value = "";
      showMessage(`${file.name} — ready to upload when you save.`);
    } else {
      showMessage("");
    }
    render();
  };
  input.addEventListener("change", selected);
  remove?.addEventListener("change", () => {
    if (remove.checked) { input.value = ""; link.value = ""; }
    invalidPhoto = false;
    showMessage(remove.checked ? "The current photo will be removed when you save." : "");
    render();
  });
  link.addEventListener("input", () => {
    if (link.value.trim()) {
      input.value = "";
      if (remove) remove.checked = false;
    }
    invalidPhoto = false;
    showMessage("");
    render();
  });
  reset.addEventListener("click", () => {
    input.value = "";
    link.value = originalLink;
    if (remove) remove.checked = false;
    invalidPhoto = false;
    showMessage("");
    render();
  });
  ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  }));
  dropzone.addEventListener("dragleave", (event) => {
    if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove("is-dragging");
  });
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragging");
    const files = event.dataTransfer.files;
    if (files.length !== 1) {
      showMessage("Drop one photo at a time.", true);
      return;
    }
    try {
      input.files = files;
      selected();
    } catch {
      showMessage("Use the Choose File button to select this photo.", true);
    }
  });
  preview.addEventListener("error", () => {
    if (input.files.length) {
      invalidPhoto = true;
      showMessage("This image could not be previewed. Choose another photo.", true);
    } else if (link.value.trim()) {
      showMessage("The image link could not be previewed. Check the link or choose a file.");
    }
  });
  window.addEventListener("pagehide", () => { if (objectUrl) URL.revokeObjectURL(objectUrl); });
  render();

  // Keep the chosen file and preview when server validation reports an error.
  if (!window.fetch) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (invalidPhoto) { input.focus(); return; }
    const button = form.querySelector("button[type=submit]");
    if (button.disabled) return;
    const body = new FormData(form);
    const label = button.innerHTML;
    button.disabled = true;
    button.textContent = "Saving…";
    try {
      const response = await fetch(form.action, {
        method: "POST", body, credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (response.redirected) { window.location.assign(response.url); return; }
      if (response.ok && response.headers.get("Content-Type")?.includes("application/json")) {
        const result = await response.json();
        window.location.assign(result.redirect_url);
        return;
      }
      const document = new DOMParser().parseFromString(await response.text(), "text/html");
      const feedback = document.querySelector("[data-item-feedback]");
      if (feedback && feedback.textContent.trim()) {
        const previous = form.querySelector("[data-item-feedback]");
        previous.replaceWith(feedback.cloneNode(true));
        const summary = form.querySelector("[data-item-feedback]");
        summary.tabIndex = -1;
        summary.focus();
        summary.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "center" });
      } else {
        showMessage(response.status === 413 ? "Choose a photo up to 5 MB." :
          response.status === 400 ? "Your form has expired. Refresh this page before saving again." :
          "We could not confirm this save. Check My items before trying again.", true);
      }
    } catch {
      showMessage("Connection interrupted. Check My items before trying again to avoid a duplicate.", true);
    } finally {
      button.disabled = false;
      button.innerHTML = label;
    }
  });
});
