// Link rows for a grouped list: a `url` row copies it, an `href` row opens it.
import { h } from "./dom.js";
import { copyText } from "./feedback.js";
import { symbol } from "./icons.js";

const COPIED_MS = 1500;

function externalRow({ label, href }) {
  return h(
    "a",
    {
      class: "cfg-cell link-row",
      href,
      target: "_blank",
      rel: "noreferrer",
    },
    h("span", { class: "cfg-label" }, label),
    h("span", { class: "link-icon" }, symbol("arrow.up.right", 18)),
  );
}

function copyRow({ label, url }) {
  const icon = h("span", { class: "link-icon" }, symbol("doc.on.doc", 18));
  const row = h(
    "button",
    {
      class: "cfg-cell link-row",
      type: "button",
      title: url,
      "aria-label": `Copy ${label}`,
    },
    h("span", { class: "cfg-label" }, label),
    icon,
  );
  row.addEventListener("click", async () => {
    await copyText(url);
    icon.replaceChildren(symbol("checkmark", 18));
    setTimeout(
      () => icon.replaceChildren(symbol("doc.on.doc", 18)),
      COPIED_MS,
    );
  });
  return row;
}

const linkRow = (link) => (link.href ? externalRow(link) : copyRow(link));

/** `links` is [{label, url | href}, ...]; returns an inset grouped list. */
export function linkRows(links) {
  if (!links.length) return null;
  return h("div", { class: "cfg-group" }, links.map(linkRow));
}
