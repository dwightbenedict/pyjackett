// "Indexers" tab: configured indexers, add dialog and configuration dialog.
import { api, paths } from "./api.js";
import { buildConfigForm } from "./config-form.js";
import { clear, h } from "./dom.js";
import { copyText, toast, withBusy } from "./feedback.js";
import { openModal } from "./modal.js";

const MAX_ADD_ROWS = 300;

export async function renderIndexers(view, state) {
  clear(view).append(h("p", { class: "muted" }, "Loading indexers…"));
  const indexers = await api.indexers(true);
  const reload = () => renderIndexers(view, state);
  clear(view).append(
    header(state, reload),
    stats(indexers),
    indexers.length
      ? grid(indexers, state, reload)
      : emptyState(state, reload),
  );
}

function feedUrl(id, apiKey) {
  return `${paths.torznab(id)}api?apikey=${apiKey}&t=search&cat=&q=`;
}

function button(label, onclick, className = "") {
  return h(
    "button",
    { class: `btn ${className}`.trim(), type: "button", onclick },
    label,
  );
}

// ---- header and summary ----

function header(state, reload) {
  return h(
    "div",
    { class: "view-head" },
    h("h1", {}, "Configured indexers"),
    h(
      "div",
      { class: "toolbar" },
      button("Copy aggregate feed", () =>
        copyText(feedUrl("all", state.apiKey), "Aggregate feed URL copied"),
      ),
      button("＋ Add indexer", () => openAddDialog(reload), "primary"),
    ),
  );
}

function statCell(value, label) {
  return h(
    "div",
    { class: "card stat" },
    h("b", {}, String(value)),
    h("span", {}, label),
  );
}

function stats(indexers) {
  const failing = indexers.filter((i) => i.failing || i.last_error).length;
  const healthy = indexers.filter((i) => i.healthy && !i.failing).length;
  const publicCount = indexers.filter((i) => i.type === "public").length;
  return h(
    "div",
    { class: "stats" },
    statCell(indexers.length, "Configured"),
    statCell(healthy, "Healthy"),
    statCell(failing, "Need attention"),
    statCell(publicCount, "Public"),
  );
}

function emptyState(state, reload) {
  return h(
    "div",
    { class: "card empty" },
    h("h2", {}, "No indexers yet"),
    h("p", {}, "Add a tracker to start serving Torznab feeds."),
    button("＋ Add indexer", () => openAddDialog(reload), "primary"),
  );
}

// ---- cards ----

function grid(indexers, state, reload) {
  return h(
    "div",
    { class: "grid" },
    indexers.map((indexer) => card(indexer, state, reload)),
  );
}

function badge(kind, label) {
  return h(
    "span",
    { class: `badge ${kind}` },
    h("i", { class: "dot" }),
    label,
  );
}

function statusBadge(indexer) {
  if (indexer.last_error) {
    return badge("danger", "Error");
  }
  if (indexer.failing) {
    return badge("warn", "Failing");
  }
  return indexer.healthy ? badge("ok", "Healthy") : badge("", "Idle");
}

function cardHeader(indexer) {
  const link = h(
    "a",
    {
      class: "indexer-link",
      href: indexer.site_link,
      target: "_blank",
      rel: "noreferrer",
    },
    indexer.site_link,
  );
  return h(
    "div",
    { class: "indexer-head" },
    h("div", {}, h("h3", {}, indexer.name), link),
    statusBadge(indexer),
  );
}

function cardBadges(indexer) {
  return h(
    "div",
    { class: "badges" },
    h("span", { class: "badge accent" }, indexer.type || "unknown"),
    h("span", { class: "badge" }, indexer.language),
    indexer.tags.map((tag) => h("span", { class: "badge" }, `#${tag}`)),
  );
}

async function runTest(event, indexer, reload) {
  await withBusy(event.currentTarget, async () => {
    try {
      await api.testIndexer(indexer.id);
      toast(`${indexer.name}: test passed`, "ok");
    } catch (error) {
      toast(`${indexer.name}: ${error.message}`, "error", 9000);
    }
  });
  reload();
}

async function removeIndexer(indexer, reload) {
  if (!confirm(`Delete the configuration of ${indexer.name}?`)) {
    return;
  }
  try {
    await api.deleteIndexer(indexer.id);
    toast(`${indexer.name} removed`, "ok");
  } catch (error) {
    toast(error.message, "error");
  }
  reload();
}

function copyActions(indexer, state) {
  const actions = [
    button("Torznab URL", () =>
      copyText(paths.torznab(indexer.id), "Torznab URL copied"),
    ),
    button("RSS feed", () =>
      copyText(feedUrl(indexer.id, state.apiKey), "Feed URL copied"),
    ),
  ];
  if (indexer.potatoenabled) {
    actions.push(
      button("Potato", () =>
        copyText(paths.potato(indexer.id), "Potato URL copied"),
      ),
    );
  }
  return actions;
}

function cardActions(indexer, state, reload) {
  const small = (label, onclick, extra = "") =>
    button(label, onclick, `small ${extra}`.trim());
  return h(
    "div",
    { class: "indexer-actions" },
    small("Search", () => {
      location.hash = `search?tracker=${indexer.id}`;
    }),
    copyActions(indexer, state).map((b) => {
      b.classList.add("small");
      return b;
    }),
    small("Test", (event) => runTest(event, indexer, reload)),
    small("Edit", () => openConfigDialog(indexer, reload)),
    small("Delete", () => removeIndexer(indexer, reload), "danger"),
  );
}

function card(indexer, state, reload) {
  return h(
    "article",
    { class: "card indexer" },
    cardHeader(indexer),
    h("p", { class: "indexer-desc" }, indexer.description),
    cardBadges(indexer),
    indexer.last_error
      ? h("div", { class: "error-note" }, indexer.last_error)
      : null,
    cardActions(indexer, state, reload),
  );
}

// ---- add dialog ----

function matchesFilter(indexer, text, type) {
  const haystack = `${indexer.name} ${indexer.description} ${indexer.language}
    ${indexer.tags.join(" ")}`.toLowerCase();
  return (!type || indexer.type === type) && haystack.includes(text);
}

function addRow(indexer, onPick) {
  return h(
    "tr",
    {},
    h("td", { class: "title-cell" }, indexer.name),
    h("td", {}, h("span", { class: "badge accent" }, indexer.type || "?")),
    h("td", {}, indexer.language),
    h("td", { class: "muted" }, indexer.description),
    h(
      "td",
      {},
      button("Add", () => onPick(indexer), "small primary"),
    ),
  );
}

function addTable(indexers, onPick) {
  if (!indexers.length) {
    return h("div", { class: "empty" }, "No indexers match your filter.");
  }
  const columns = ["Name", "Type", "Language", "Description", ""];
  return h(
    "table",
    {},
    h(
      "thead",
      {},
      h(
        "tr",
        {},
        columns.map((t) => h("th", {}, t)),
      ),
    ),
    h(
      "tbody",
      {},
      indexers.slice(0, MAX_ADD_ROWS).map((i) => addRow(i, onPick)),
    ),
  );
}

function addFilters() {
  const query = h("input", {
    type: "search",
    placeholder: "Search by name, language or tag…",
  });
  const options = ["public", "semi-public", "private"];
  const type = h(
    "select",
    {},
    h("option", { value: "" }, "All types"),
    options.map((t) => h("option", { value: t }, t)),
  );
  return { query, type };
}

async function openAddDialog(reload) {
  const all = (await api.indexers()).filter((i) => !i.configured);
  const { query, type } = addFilters();
  const list = h("div", { class: "table-wrap" });
  const toolbar = h(
    "div",
    { class: "toolbar", style: "margin-bottom:14px" },
    query,
    type,
  );
  const modal = openModal({
    title: "Add indexer",
    wide: true,
    body: [toolbar, list],
  });
  const draw = () => {
    const text = query.value.trim().toLowerCase();
    const matches = all.filter((i) => matchesFilter(i, text, type.value));
    clear(list).append(
      addTable(matches, (indexer) => {
        modal.close();
        openConfigDialog(indexer, reload);
      }),
    );
  };
  query.addEventListener("input", draw);
  type.addEventListener("change", draw);
  draw();
}

// ---- configuration dialog ----

function saveHandler(context) {
  const { indexer, modal, message, getForm, mount, reload } = context;
  return async (event) => {
    await withBusy(event.currentTarget, async () => {
      message.hidden = true;
      try {
        await api.saveIndexerConfig(indexer.id, getForm().values());
        modal.close();
        toast(`${indexer.name} configured`, "ok");
        reload();
      } catch (error) {
        message.textContent = error.message;
        message.hidden = false;
        if (error.config) {
          mount(error.config); // e.g. a captcha to solve
        }
      }
    });
  };
}

async function openConfigDialog(indexer, reload) {
  let form;
  const body = h("div", {});
  const message = h("div", { class: "form-error", hidden: true });
  const mount = (items) => {
    form = buildConfigForm(items);
    clear(body).append(form.form);
  };
  try {
    mount(await api.indexerConfig(indexer.id));
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  const save = button("Save", null, "primary");
  const modal = openModal({
    title: `Configure ${indexer.name}`,
    body: [body, message],
    footer: [button("Cancel", () => modal.close()), save],
  });
  const getForm = () => form;
  save.addEventListener(
    "click",
    saveHandler({ indexer, modal, message, getForm, mount, reload }),
  );
}
