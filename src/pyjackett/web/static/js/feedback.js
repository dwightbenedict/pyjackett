// User feedback: clipboard and busy buttons.
import { h } from "./dom.js";
import { spinner, symbol } from "./icons.js";

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

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    legacyCopy(text);
  }
}

const COPIED_MS = 1500;

/**
 * Label of a copy button: `label` at rest, a checkmark and "Copied" for a
 * moment after copying. Both states share one grid cell, so the button is as
 * wide as the wider of the two from the start and never resizes when copied.
 */
export function copyLabel(label = "Copy") {
  return h(
    "span",
    { class: "copy-label" },
    h("span", { class: "copy-rest" }, label),
    h("span", { class: "copy-done" }, symbol("checkmark", 14, 2.4), "Copied"),
  );
}

/** Copy `text`, then show the "Copied" state of a `copyLabel` button. */
export async function copyWithConfirmation(button, text) {
  await copyText(text);
  if (button.dataset.copied) return;
  button.dataset.copied = "true";
  setTimeout(() => delete button.dataset.copied, COPIED_MS);
}

// Quick actions finish before a spinner would be worth showing.
const SPINNER_DELAY_MS = 150;

/**
 * Run an async action with the button disabled. A spinner replaces its
 * content only if the action is still running after a short delay.
 */
export async function withBusy(button, action) {
  const indicator = spinner();
  const showSpinner = () => {
    button.classList.add("busy");
    button.append(indicator);
  };
  button.disabled = true;
  button.classList.add("working");
  const timer = setTimeout(showSpinner, SPINNER_DELAY_MS);
  try {
    return await action();
  } finally {
    clearTimeout(timer);
    button.disabled = false;
    button.classList.remove("working", "busy");
    indicator.remove();
  }
}
