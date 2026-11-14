// Modal dialogs.
import { h } from "./dom.js";
import { symbol } from "./icons.js";

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
    symbol("xmark", 16, 2.2),
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

function alertButton(label, className, onclick) {
  return h(
    "button",
    { class: `alert-btn ${className}`, type: "button", onclick },
    label,
  );
}

/**
 * Apple-style alert; resolves with `read()` when the confirm button is
 * chosen and with null when cancelled. `cancelLabel: null` hides Cancel.
 */
function showAlert({
  title,
  message,
  field = null,
  confirmLabel = "OK",
  cancelLabel = "Cancel",
  destructive = false,
  read = () => true,
}) {
  const previous = document.activeElement;
  return new Promise((resolve) => {
    const finish = (answer) => {
      backdrop.remove();
      document.removeEventListener("keydown", onKey);
      if (previous instanceof HTMLElement) previous.focus();
      resolve(answer);
    };
    const onKey = (event) => {
      if (event.key === "Escape") finish(null);
      if (event.key === "Enter" && event.target === field) finish(read());
    };
    const confirm = alertButton(
      confirmLabel,
      destructive ? "destructive" : "default",
      () => finish(read()),
    );
    const backdrop = h(
      "div",
      { class: "modal-backdrop" },
      h(
        "div",
        {
          class: "alert",
          role: "alertdialog",
          "aria-modal": "true",
          "aria-label": title,
        },
        h(
          "div",
          { class: "alert-text" },
          h("h2", {}, title),
          message && h("p", {}, message),
          field,
        ),
        h(
          "div",
          { class: "alert-actions" },
          cancelLabel &&
            alertButton(cancelLabel, "default", () => finish(null)),
          confirm,
        ),
      ),
    );
    document.getElementById("modal-root").append(backdrop);
    document.addEventListener("keydown", onKey);
    (field ?? confirm).focus();
  });
}

/** Resolves true when the confirm button is chosen. */
export async function confirmDialog(options) {
  return (await showAlert(options)) === true;
}

/** One-button alert for errors and notices. */
export async function alertDialog({ title, message }) {
  await showAlert({ title, message, cancelLabel: null });
}

/** Alert with a secure text field; resolves with the text or null. */
export function passwordDialog({ title, message, confirmLabel = "OK" }) {
  const field = h("input", {
    type: "password",
    class: "alert-field",
    autocomplete: "current-password",
    "aria-label": "Password",
    placeholder: "Password",
  });
  return showAlert({
    title,
    message,
    field,
    confirmLabel,
    read: () => field.value,
  });
}
