// Wraps a search input with the round clear button of iOS search fields.
import { h } from "./dom.js";
import { symbol } from "./icons.js";

export function searchField(input) {
  const button = h(
    "button",
    {
      class: "clear-btn",
      type: "button",
      "aria-label": "Clear Text",
      hidden: true,
    },
    symbol("xmark", 10, 3.2),
  );
  const sync = () => {
    button.hidden = !input.value;
  };
  button.addEventListener("click", () => {
    input.value = "";
    sync();
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  });
  input.addEventListener("input", sync);
  sync();
  return h("div", { class: "search-field" }, input, button);
}
