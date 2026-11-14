// Dialog that builds an RSS (Torznab) feed URL from indexer filters.
import { paths } from "./api.js";
import { standardCategories } from "./categories.js";
import { clear, h } from "./dom.js";
import { copyText } from "./feedback.js";
import { openModal } from "./modal.js";

const STATUSES = ["healthy", "failing", "unknown"];

export function feedUrl(id, apiKey, { categories = "", query = "" } = {}) {
  const cat = encodeURIComponent(categories);
  const q = encodeURIComponent(query);
  return `${paths.torznab(id)}api?apikey=${apiKey}&t=search&cat=${cat}&q=${q}`;
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

function labelled(text, control) {
  return h("label", { class: "field" }, h("span", {}, text), control);
}

function capitalized(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Options are [value, label] pairs; none at all disables the select. */
function anySelect(options, emptyLabel = "Any") {
  const select = h(
    "select",
    {},
    h("option", { value: "" }, options.length ? "Any" : emptyLabel),
    options.map(([value, label]) => h("option", { value }, label)),
  );
  select.disabled = !options.length;
  return select;
}

const plain = (value) => [value, value];
const titled = (value) => [value, capitalized(value)];
function selectedValues(select) {
  return [...select.selectedOptions]
    .map((o) => o.value)
    .filter(Boolean)
    .join(",");
}

/** "All" is selected exactly when no specific category is. */
function keepAllOption(select) {
  const [all, ...rest] = select.options;
  const specific = rest.some((o) => o.selected);
  if (all.selected && specific && select.dataset.hadAll !== "false") {
    all.selected = false;
  } else if (all.selected && specific) {
    rest.forEach((o) => (o.selected = false));
  }
  all.selected = !rest.some((o) => o.selected);
  select.dataset.hadAll = String(all.selected);
}

/** The filter expression for the chosen components, e.g. tag:x+lang:en. */
function filterExpression(controls) {
  const parts = ["type", "lang", "tag", "status"]
    .filter((name) => controls[name].value)
    .map((name) => `${name}:${controls[name].value}`);
  return parts.length ? parts.join("+") : "all";
}

const PARAM_LABELS = {
  apikey: "API Key",
  t: "Function",
  cat: "Categories",
  q: "Query",
};

function urlRow(label, value, key) {
  return h(
    "div",
    { class: "feed-row" },
    h("dt", {}, label, key ? h("code", {}, ` ${key}`) : null),
    h("dd", {}, value || h("span", { class: "muted" }, "(none)")),
  );
}

/** Path segments, with the one naming the indexer or filter in bold. */
function pathValue(pathname, filter) {
  const marked = encodeURIComponent(filter);
  return pathname
    .split("/")
    .filter(Boolean)
    .map((segment) => [
      "/",
      h("wbr"),
      segment === marked ? h("b", {}, segment) : segment,
    ]);
}

/** Draw the feed URL as labelled parts: server, path, filter, query. */
function showUrl(element, url, filter) {
  const parsed = new URL(url);
  const params = [...parsed.searchParams].map(([key, value]) =>
    urlRow(PARAM_LABELS[key] || key, value, key),
  );
  clear(element).append(
    urlRow("Server", parsed.origin),
    urlRow("Path", pathValue(parsed.pathname, filter)),
    urlRow("Indexer Filter", filter),
    ...params,
  );
}

function buildControls(indexers) {
  const configured = indexers.filter((i) => i.configured);
  return {
    type: anySelect(uniqueSorted(configured.map((i) => i.type)).map(titled)),
    lang: anySelect(
      uniqueSorted(configured.map((i) => i.language)).map(plain),
    ),
    tag: anySelect(
      uniqueSorted(configured.flatMap((i) => i.tags)).map(plain),
      "No Tags",
    ),
    status: anySelect(STATUSES.map(titled)),
    categories: h(
      "select",
      { multiple: true, size: 6 },
      h("option", { value: "", selected: true }, "All"),
      standardCategories(configured).map(([id, name]) =>
        h("option", { value: id }, name),
      ),
    ),
    query: h("input", { type: "search", placeholder: "Optional keywords" }),
  };
}

export function openFeedDialog(indexers, apiKey) {
  const controls = buildControls(indexers);
  const output = h("dl", { class: "feed-url" });
  let url = "";
  const update = () => {
    const filter = filterExpression(controls);
    url = feedUrl(filter, apiKey, {
      categories: selectedValues(controls.categories),
      query: controls.query.value.trim(),
    });
    showUrl(output, url, filter);
  };
  for (const control of Object.values(controls)) {
    control.addEventListener("input", update);
  }
  controls.categories.addEventListener("input", () =>
    keepAllOption(controls.categories),
  );
  update();
  const copy = h(
    "button",
    {
      class: "btn primary",
      type: "button",
      onclick: () => copyText(url),
    },
    "Copy Feed URL",
  );
  openModal({
    title: "RSS Feed",
    body: [
      h(
        "div",
        { class: "two-col" },
        labelled("Type", controls.type),
        labelled("Language", controls.lang),
        labelled("Tag", controls.tag),
        labelled("Status", controls.status),
      ),
      labelled("Categories", controls.categories),
      labelled("Query", controls.query),
      h("div", { class: "field" }, h("span", {}, "Feed URL"), output),
    ],
    footer: [copy],
  });
}
