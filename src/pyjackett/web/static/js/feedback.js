// User feedback: toasts, clipboard and busy buttons.
import { h } from "./dom.js";

export function toast(message, kind = "info", milliseconds = 4200) {
  const element = h("div", { class: `toast ${kind}` }, message);
  document.getElementById("toasts").append(element);
  setTimeout(() => element.remove(), milliseconds);
}

function legacyCopy(text) {
  const area = h("textarea", {
    value: text,
    style: "position:fixed;opacity:0",
  });
  document.body.append(area);
  area.select();
  const done = document.execCommand("copy");
  area.remove();
  return done;
}

export async function copyText(text, label = "Copied to clipboard") {
  let copied;
  try {
    await navigator.clipboard.writeText(text);
    copied = true;
  } catch {
    copied = legacyCopy(text);
  }
  toast(copied ? label : "Copy failed", copied ? "ok" : "error");
}

/** Run an async action while disabling a button. */
export async function withBusy(button, action) {
  button.disabled = true;
  try {
    return await action();
  } finally {
    button.disabled = false;
  }
}
