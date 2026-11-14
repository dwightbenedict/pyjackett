// Renders an indexer configuration (list of typed items) as a form.
import { h } from "./dom.js";

// Short Title Case replacements for the wordiest labels in definitions.
const SHORT_LABELS = {
  "Use filename as title for single file releases": "Filename as Title",
  "Replace MULTi by this language": "MULTi Language",
  "Replace MULTi by another language in release name": "MULTi Language",
  "Replace VOSTFR and SUBFRENCH with ENGLISH": "VOSTFR as English",
  "Replace VFQ with FRENCH": "VFQ as French",
  "Sort requested from site": "Sort",
  "Order requested from site": "Order",
  "Search freeleech only": "Freeleech Only",
  "Search FreeLeech only": "Freeleech Only",
  "Filter freeleech only": "Freeleech Only",
  "Search freeleech and 50% freeleech only": "Freeleech and 50%",
  "Filter OnlyUpload only": "OnlyUpload Only",
  "Search OnlyUpload": "OnlyUpload Only",
  "Use SeedBox Download Link": "Seedbox Link",
  "Strip Cyrillic Letters": "Strip Cyrillic",
  "Account Inactivity": "Inactivity",
  "Site Link": "URL",
};

// Capitalise every word; leave acronyms and mixed-case names (APIKey,
// MULTi, 2FA) as written.
function titleCase(text) {
  return text.replace(/[^\s-]+/g, (word) =>
    /[A-Z0-9]/.test(word.slice(1))
      ? word
      : word.replace(/[A-Za-z]/, (letter) => letter.toUpperCase()),
  );
}

const LABEL_LIMIT = 40;
// Where a sentence-like label turns from the name into its explanation.
const LABEL_BREAKS = [" - ", ": ", " (", ", ", ". "];
const LABEL_CONNECTORS = [" to ", " by ", " from ", " for ", " as "];

function splitAt(text, separators) {
  const cuts = separators
    .map((separator) => [text.indexOf(separator), separator])
    .filter(([index]) => index > 0);
  if (!cuts.length) return null;
  const [index, separator] = cuts.sort((a, b) => a[0] - b[0])[0];
  return [text.slice(0, index), text.slice(index + separator.length)];
}

// Drops the bracket that opened the explanation and tidies its start.
const sentence = (text) =>
  text
    .replace(/^[\s(]+|[\s)]+$/g, "")
    .replace(/^([^(]*)\)/, "$1")
    .replace(/^./, (c) => c.toUpperCase());

/** A long label becomes a short title plus an explanation line. */
function splitLabel(name) {
  let [title, detail] = splitAt(name, LABEL_BREAKS) || [name, ""];
  if (title.length > LABEL_LIMIT) {
    const [head, rest] = splitAt(title, LABEL_CONNECTORS) || [title, ""];
    title = head;
    detail = [rest, detail].filter(Boolean).join(". ");
  }
  return {
    title: titleCase(SHORT_LABELS[title] || title),
    detail: sentence(detail),
  };
}

const shortLabel = (name) => splitLabel(name).title;

function labelNode(name, tag = "span") {
  const { title, detail } = splitLabel(name);
  return h(
    tag,
    { class: "cfg-label" },
    h("span", {}, title),
    detail ? h("small", { class: "cfg-detail" }, detail) : null,
  );
}

// "About your API Key" -> "API Key".
function helpTitle(name) {
  return titleCase(
    name.replace(/^(About( your| the)?|How to get( the)?)\s+/i, "").trim(),
  );
}

// Definitions do not say which fields are mandatory, so credentials are
// assumed to be required and everything else optional.
const REQUIRED_LABEL =
  /user ?name|password|cookie|api ?key|pass ?key|token|e-?mail|\b(pid|uid)\b/i;

const placeholderFor = (item) =>
  REQUIRED_LABEL.test(item.name) ? "Required" : "Optional";

/** Each renderer returns {node, read(item) -> updated item}. */
const RENDERERS = {
  inputstring: (item) => {
    const input = h("input", {
      type: "text",
      value: item.value ?? "",
      placeholder: placeholderFor(item),
    });
    return field(item, input, () => ({ ...item, value: input.value }));
  },
  password: (item) => {
    const input = h("input", {
      type: "password",
      value: item.value ?? "",
      autocomplete: "new-password",
      placeholder: placeholderFor(item),
    });
    return field(item, input, () => ({ ...item, value: input.value }));
  },
  inputtags: (item) => {
    const input = h("input", {
      type: "text",
      value: item.value ?? "",
      placeholder: placeholderFor(item),
    });
    return field(item, input, () => ({ ...item, value: input.value }));
  },
  inputbool: (item) => {
    const box = h("input", { type: "checkbox", checked: !!item.value });
    const node = h(
      "label",
      { class: "cfg-cell switch" },
      box,
      labelNode(item.name),
    );
    return { node, read: () => ({ ...item, value: box.checked }) };
  },
  inputselect: (item) => {
    const select = h(
      "select",
      {},
      Object.entries(item.options || {}).map(([value, label]) =>
        h("option", { value, selected: value === item.value }, label),
      ),
    );
    return field(item, select, () => ({ ...item, value: select.value }));
  },
  inputcheckbox: (item) => {
    const chosen = new Set(item.values || []);
    const boxes = Object.entries(item.options || {}).map(([value, label]) => {
      const box = h("input", {
        type: "checkbox",
        value,
        checked: chosen.has(value),
      });
      return { box, row: h("label", {}, box, label) };
    });
    const list = h(
      "div",
      { class: "check-list" },
      boxes.map((entry) => entry.row),
    );
    const read = () => ({
      ...item,
      values: boxes
        .filter((entry) => entry.box.checked)
        .map((entry) => entry.box.value),
    });
    return field(item, list, read, true);
  },
  displayimage: (item) => ({
    node: h(
      "div",
      { class: "cfg-cell stack" },
      h("span", {}, item.name),
      h("img", { src: item.value, alt: item.name }),
    ),
    read: () => item,
  }),
};

function field(item, control, read, stacked = false) {
  const className = stacked ? "cfg-cell stack" : "cfg-cell";
  const tag = stacked ? "div" : "label";
  const label = labelNode(item.name);
  return { node: h(tag, { class: className }, label, control), read };
}

const isDocumentation = (item) => item.type === "displayinfo";

function renderItem(item) {
  const render = RENDERERS[item.type];
  return render ? render(item) : { node: null, read: () => item };
}

// ---- documentation ----

function helpBody(item) {
  const body = h("div", { class: "cfg-doc-body" });
  body.innerHTML = item.value || ""; // trusted help text from the server
  return body;
}

// Every help entry sits behind a chevron row, however short.
function documentEntry(item) {
  return h(
    "details",
    { class: "cfg-disclosure" },
    h("summary", {}, helpTitle(item.name)),
    helpBody(item),
  );
}

function documentation(items) {
  if (!items.length) return null;
  return h(
    "div",
    { class: "cfg-docs" },
    h("div", { class: "cfg-group" }, items.map(documentEntry)),
  );
}

/**
 * Build the form and, separately, the indexer documentation.
 * `values()` returns every item to post back.
 */
export function buildConfigForm(items) {
  const docs = items.filter(isDocumentation);
  const fields = items.filter((item) => !isDocumentation(item));
  const parts = fields.map(renderItem);
  const form = h(
    "form",
    { onsubmit: (event) => event.preventDefault() },
    parts.length
      ? h(
          "div",
          { class: "cfg-group" },
          parts.map((part) => part.node),
        )
      : null,
  );
  return {
    form,
    docs: documentation(docs),
    values: () => [...parts.map((part) => part.read()), ...docs],
  };
}
