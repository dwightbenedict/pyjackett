// Modal dialogs.
import { h } from "./dom.js";

const FOCUSABLE = "input, select, textarea, button.primary";

function dialogHead(title, close) {
  const closeButton = h(
    "button",
    {
      class: "icon-btn",
      type: "button",
      "aria-label": "Close",
      onclick: close,
    },
    "✕",
  );
  return h("div", { class: "modal-head" }, h("h2", {}, title), closeButton);
}

function dialogElement({ title, wide, bodyElement, footerElement }, close) {
  return h(
    "div",
    {
      class: `modal${wide ? " wide" : ""}`,
      role: "dialog",
      "aria-modal": "true",
      "aria-label": title,
    },
    dialogHead(title, close),
    bodyElement,
    footerElement,
  );
}

/** Show a dialog; returns handles {close, body, footer}. */
export function openModal({ title, body, footer, wide = false, onClose }) {
  const previous = document.activeElement;
  const bodyElement = h("div", { class: "modal-body" }, body);
  const footerElement = footer
    ? h("div", { class: "modal-foot" }, footer)
    : null;
  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    if (previous instanceof HTMLElement) {
      previous.focus();
    }
    onClose?.();
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      close();
    }
  };
  const dialog = dialogElement(
    { title, wide, bodyElement, footerElement },
    close,
  );
  const backdrop = h(
    "div",
    {
      class: "modal-backdrop",
      onmousedown: (event) => event.target === backdrop && close(),
    },
    dialog,
  );
  document.getElementById("modal-root").append(backdrop);
  document.addEventListener("keydown", onKey);
  dialog.querySelector(FOCUSABLE)?.focus();
  return { close, body: bodyElement, footer: footerElement };
}
