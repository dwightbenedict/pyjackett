// "Indexers" tab: all indexers and the configuration dialog.
import { actionMenu } from "./action-menu.js";
import { api, paths } from "./api.js";
import { buildConfigForm } from "./config-form.js";
import { clear, h, measure } from "./dom.js";
import { withBusy } from "./feedback.js";
import { durationParts } from "./format.js";
import { feedUrl, openFeedDialog } from "./feed-dialog.js";
import { iconButton } from "./icons.js";
import {
  Selection,
  selectAllButton,
  selectMark,
  selectionActions,
  selectionTitle,
} from "./indexer-selection.js";
import { linkRows } from "./link-rows.js";
import { confirmDialog, openModal } from "./modal.js";
import {
  ALL_KEY,
  CONFIGURED_KEY,
  invalidate,
  loadStale,
  remember,
} from "./stale-cache.js";
import { statusFilter } from "./status-filter.js";
import { hideOnScrollDown } from "./sticky-bar.js";

const ADDED = { configured: true, healthy: false, failing: false };
const REMOVED = { configured: false, healthy: false, failing: false };

// iPad and Mac widths: the select-mode actions move to the top toolbar.
const WIDE = window.matchMedia("(min-width: 700px)");
let onLayoutChange = () => {};
WIDE.addEventListener("change", () => onLayoutChange());

// The page stays alive while another tab is shown: coming back only
// revalidates the list and redraws if something changed meanwhile.
const instances = new WeakMap();

export async function renderIndexers(view, state) {
  const live = instances.get(view);
  if (live) return live();
  let current = [];
  let stale = false;
  const draw = () => {
    stale = false;
    drawIndexers(view, state, sync, current);
  };
  const show = (indexers) => {
    current = indexers;
    if (view.hidden) stale = true;
    else draw();
    watchRunningTests(view, sync);
  };
  onLayoutChange = () => state.indexerSelection && show(current);
  const redraw = (indexer) => {
    if (!redrawCard(view, indexer, state, sync)) draw();
  };
  // A status change touches the dot only, unless filters now hide the card.
  const redrawStatus = (indexer) =>
    updateStatus(view, indexer, state) || redraw(indexer);
  const patch = (indexer, fields, statusOnly = false) => {
    Object.assign(indexer, { last_error: null, ...fields });
    invalidate(CONFIGURED_KEY);
    remember(ALL_KEY, current);
    (statusOnly ? redrawStatus : redraw)(indexer);
  };
  // Merge the (smaller) configured list instead of refetching everything.
  const refreshConfigured = async () => {
    const fresh = await api.indexers(true).catch(() => []);
    const changed = mergeConfigured(current, fresh);
    invalidate(CONFIGURED_KEY);
    remember(ALL_KEY, current);
    changed.forEach(redrawStatus);
  };
  const reload = () => {
    invalidate(CONFIGURED_KEY);
    invalidate(ALL_KEY);
    return load();
  };
  const setTesting = (ids, on) => markTesting(view, current, ids, on);
  const sync = {
    patch,
    patchStatus: (indexer, fields) => patch(indexer, fields, true),
    refreshConfigured,
    reload,
    draw,
    setTesting,
    all: () => current,
  };
  // Draws on first load, after a reload, or when a hidden change is pending.
  const load = async () => {
    const before = current;
    current = await loadStale(ALL_KEY, () => api.indexers(), show);
    if (current !== before || stale) draw();
    watchRunningTests(view, sync);
  };
  instances.set(view, load);
  try {
    await load();
  } catch (error) {
    instances.delete(view);
    throw error;
  }
}

const TEST_POLL_MS = 1500;
let testPoll = null;

// Tests belong to the server, so after a reload some may still be running:
// keep their dots blinking and settle each one when its test ends.
function watchRunningTests(view, sync) {
  clearTimeout(testPoll);
  const running = sync.all().some((i) => i.testing);
  if (!running || view.hidden) return;
  testPoll = setTimeout(async () => {
    await sync.refreshConfigured();
    watchRunningTests(view, sync);
  }, TEST_POLL_MS);
}

// What a card shows of an indexer's status: dot, latency and error note.
const shownStatus = (indexer) =>
  JSON.stringify([
    statusOf(indexer),
    indexer.latency_ms ?? null,
    indexer.last_error || "",
  ]);

/**
 * Fold fresh server state into the known indexers. Returns those whose
 * shown status changed; the rest are already on screen as they should be.
 */
function mergeConfigured(known, fresh) {
  const changed = [];
  fresh.forEach((item) => {
    const match = known.find((i) => i.id === item.id);
    if (!match) return;
    const before = shownStatus(match);
    Object.assign(match, item);
    if (shownStatus(match) !== before) changed.push(match);
  });
  return changed;
}

/**
 * Update the status dot and error note of a card without replacing it.
 * False when the card is not on screen or the filters no longer show it.
 */
function updateStatus(view, indexer, state) {
  const card = view.querySelector(`[data-id="${CSS.escape(indexer.id)}"]`);
  const filters = state.indexerFilters || DEFAULT_FILTERS;
  if (!card || !matchesFilters(indexer, filters)) return false;
  card.querySelector(".status-dot").replaceWith(statusDot(indexer));
  card.querySelector(".latency")?.remove();
  const latency = latencyLabel(indexer);
  if (latency) card.querySelector(".badges").append(latency);
  card.querySelector(".error-note")?.remove();
  if (indexer.last_error) {
    card.append(h("div", { class: "error-note" }, indexer.last_error));
  }
  return true;
}

// Blink the dots in place; a redraw would replay the card's animation.
function markTesting(view, indexers, ids, on) {
  ids.forEach((id) => {
    const known = indexers.find((i) => i.id === id);
    if (known) known.testingHere = on;
    view
      .querySelector(`[data-id="${CSS.escape(id)}"] .status-dot`)
      ?.classList.toggle("testing", on || Boolean(known?.testing));
  });
}

/**
 * Swap one card in place, or drop it if the filters now hide it. Returns
 * false when the whole list needs drawing instead.
 */
function redrawCard(view, indexer, state, sync) {
  const old = view.querySelector(`[data-id="${CSS.escape(indexer.id)}"]`);
  if (!old) return false;
  if (matchesFilters(indexer, state.indexerFilters)) {
    const fresh = card(indexer, state, sync);
    fresh.classList.add("settle");
    old.replaceWith(fresh);
    return true;
  }
  old.remove();
  return view.querySelector(".card.indexer") !== null;
}

function drawIndexers(view, state, sync, indexers) {
  const filters = (state.indexerFilters ||= { ...DEFAULT_FILTERS });
  const list = h("div", {});
  const showList = () =>
    clear(list).append(visibleList(indexers, filters, state, sync));
  showList();
  const bar = indexers.length ? filterBar(indexers, filters, showList) : null;
  const visible = () => indexers.filter((i) => matchesFilters(i, filters));
  state.indexerSelection?.listen("cards", () =>
    syncCards(view, state.indexerSelection),
  );
  const controls = state.indexerSelection
    ? selectionActions({
        selection: state.indexerSelection,
        indexers: sync.all,
        sync,
      })
    : null;
  // Phones get a floating bottom toolbar; iPad and Mac keep it on top.
  const onTop = WIDE.matches;
  const floating =
    controls && !onTop
      ? h("div", { class: "selection-bar glass" }, controls)
      : null;
  clear(view).append(
    ...[
      header(state, indexers, sync, visible, onTop ? controls : null),
      bar,
      list,
      floating ? h("div", { class: "selection-space" }) : null,
      floating,
    ].filter(Boolean),
  );
  if (bar) hideOnScrollDown(bar);
}

function visibleList(indexers, filters, state, sync) {
  if (!indexers.length) return emptyState();
  const shown = indexers.filter((i) => matchesFilters(i, filters));
  return shown.length
    ? grid(shown, state, sync)
    : emptyState("No Indexers Match the Filters");
}

function button(label, onclick, className = "") {
  return h(
    "button",
    { class: `btn ${className}`.trim(), type: "button", onclick },
    label,
  );
}

// ---- header ----

function toggleSelecting(state, sync) {
  state.indexerSelection = state.indexerSelection ? null : new Selection();
  sync.draw();
}

// Select mode follows Mail: "N Selected" title, Select All and Done above.
function header(state, indexers, sync, visible, inline = null) {
  const selection = state.indexerSelection;
  const toggle = (label, className = "") =>
    h(
      "button",
      {
        class: `bar-btn ${className}`.trim(),
        type: "button",
        onclick: () => toggleSelecting(state, sync),
      },
      label,
    );
  const controls = selection
    ? [inline, selectAllButton(selection, visible), toggle("Done", "strong")]
    : [indexers.length ? toggle("Select") : null];
  const rss = iconButton("dot.radiowaves.up.forward", "RSS Feed", () =>
    openFeedDialog(indexers, state.apiKey),
  );
  return h(
    "div",
    { class: "view-head" },
    selection
      ? selectionTitle(selection)
      : h("div", { class: "head-title" }, h("h1", {}, "Indexers"), rss),
    h("div", { class: "toolbar glass" }, controls),
  );
}

// ---- filters ----

const DEFAULT_FILTERS = { text: "", status: "", type: "", language: "" };

// The dot kinds match the dots on the cards, so the menu is a legend.
const STATUS_FILTERS = [
  ["added", "Added", "added"],
  ["available", "Disabled", ""],
  ["healthy", "Healthy", "ok"],
  ["attention", "Failing", "danger"],
];

const STATUS_MATCHERS = {
  added: (i) => i.configured,
  available: (i) => !i.configured,
  healthy: (i) => i.configured && i.healthy && !i.failing,
  attention: (i) => i.configured && (i.failing || i.last_error),
};

function matchesText(indexer, text) {
  const needle = text.trim().toLowerCase();
  if (!needle) return true;
  const haystack = [indexer.name, indexer.description, ...indexer.tags];
  return haystack.join(" ").toLowerCase().includes(needle);
}

function matchesFilters(indexer, filters) {
  const { text, status, type, language } = filters;
  return (
    matchesText(indexer, text) &&
    (!status || STATUS_MATCHERS[status](indexer)) &&
    (!type || indexer.type === type) &&
    (!language || indexer.language === language)
  );
}

function filterSelect(label, options, filters, key, onChange) {
  const select = h(
    "select",
    { "aria-label": label },
    h("option", { value: "" }, label),
    options.map(([value, text]) => h("option", { value }, text)),
  );
  select.value = filters[key];
  select.addEventListener("change", () => {
    filters[key] = select.value;
    onChange();
  });
  return select;
}

const capitalized = (text) => text.charAt(0).toUpperCase() + text.slice(1);

function distinct(indexers, field, label = (value) => value) {
  const values = new Set(indexers.map((i) => i[field]).filter(Boolean));
  return [...values].sort().map((value) => [value, label(value)]);
}

function filterBar(indexers, filters, onChange) {
  const search = h("input", {
    type: "search",
    placeholder: "Filter indexers",
    "aria-label": "Filter indexers",
  });
  search.value = filters.text;
  search.addEventListener("input", () => {
    filters.text = search.value;
    onChange();
  });
  const select = (label, options, key) =>
    filterSelect(label, options, filters, key, onChange);
  return h(
    "div",
    { class: "filter-bar" },
    search,
    h(
      "div",
      { class: "filter-selects" },
      statusFilter("Status", STATUS_FILTERS, filters, "status", onChange),
      select("Type", distinct(indexers, "type", capitalized), "type"),
      select("Language", distinct(indexers, "language"), "language"),
    ),
  );
}

function emptyState(title = "No Indexers Available") {
  return h("div", { class: "card empty" }, h("h2", {}, title));
}

// ---- cards ----

function grid(indexers, state, sync) {
  return h(
    "div",
    { class: "grid" },
    indexers.map((indexer) => card(indexer, state, sync)),
  );
}

function statusOf(indexer) {
  if (!indexer.configured) return ["", "Not Added"];
  if (indexer.testing || indexer.testingHere) return ["testing", "Testing"];
  if (indexer.last_error) return ["danger", "Error"];
  if (indexer.failing) return ["warn", "Failing"];
  return indexer.healthy ? ["ok", "Healthy"] : ["added", "Added"];
}

function statusDot(indexer) {
  const [kind, label] = statusOf(indexer);
  return h("i", {
    class: `dot status-dot ${kind}`.trim(),
    title: label,
    role: "img",
    "aria-label": label,
  });
}

// The last recorded latency of an added indexer, as quiet secondary text.
function latencyLabel(indexer) {
  const ms = indexer.latency_ms;
  if (!indexer.configured || ms === null || ms === undefined) return null;
  return h("span", { class: "latency" }, measure(durationParts(ms)));
}

function cardBadges(indexer) {
  return h(
    "div",
    { class: "badges" },
    h("span", { class: "badge" }, indexer.type || "unknown"),
    h("span", { class: "badge" }, indexer.language),
    indexer.tags.map((tag) => h("span", { class: "badge" }, `#${tag}`)),
    latencyLabel(indexer),
  );
}

function cardHeader(indexer, menu, leading = null) {
  return h(
    "div",
    { class: "indexer-head" },
    leading,
    h(
      "div",
      { class: "indexer-title" },
      h("h3", {}, statusDot(indexer), indexer.name),
      cardBadges(indexer),
    ),
    menu,
  );
}

// Tests from the card menu; the card's blinking status dot shows progress,
// the same as when several indexers are tested at once.
async function runTest(event, indexer, sync) {
  if (indexer.testingHere) return;
  const card = event.currentTarget.closest(".card");
  card.querySelector(".error-note")?.remove();
  indexer.last_error = "";
  await whileBlinking(indexer, sync, () =>
    api.testIndexer(indexer.id).catch(() => {}),
  );
  await sync.refreshConfigured();
}

// Card actions show progress on the status dot, never on their buttons.
async function whileBlinking(indexer, sync, work) {
  sync.setTesting([indexer.id], true);
  try {
    return await work();
  } finally {
    sync.setTesting([indexer.id], false);
  }
}

// Adds with the default config; indexers needing credentials open the dialog.
async function quickAdd(event, indexer, state, sync) {
  if (indexer.testingHere) return;
  const saved = await whileBlinking(indexer, sync, () =>
    api.addIndexer(indexer.id).then(
      () => true,
      () => false,
    ),
  );
  if (saved) sync.patch(indexer, ADDED);
  else openConfigDialog(indexer, state, sync);
}

async function removeIndexer(event, indexer, sync) {
  if (indexer.testingHere) return;
  const sure = await confirmDialog({
    title: `Disable ${indexer.name}?`,
    message: "It won't be searched, and its settings will be cleared.",
    confirmLabel: "Disable",
    destructive: true,
  });
  if (!sure) return;
  await whileBlinking(indexer, sync, () =>
    api.deleteIndexer(indexer.id).catch(() => {}),
  );
  sync.patch(indexer, REMOVED);
}

function indexerLinks(indexer, state) {
  const links = indexer.site_link
    ? [{ label: "Website", href: indexer.site_link }]
    : [];
  if (!indexer.configured) return links;
  links.push(
    { label: "Torznab URL", url: paths.torznab(indexer.id) },
    { label: "RSS Feed", url: feedUrl(indexer.id, state.apiKey) },
  );
  if (indexer.potatoenabled) {
    links.push({ label: "TorrentPotato", url: paths.potato(indexer.id) });
  }
  return links;
}

// Added indexers get a menu; the others a quiet "+", as in Apple Music.
function cardMenu(indexer, state, sync) {
  if (!indexer.configured) {
    return h(
      "div",
      { class: "action-menu" },
      iconButton("plus", "Add", (event) =>
        quickAdd(event, indexer, state, sync),
      ),
    );
  }
  return actionMenu("More", [
    {
      label: "Configure",
      onclick: () => openConfigDialog(indexer, state, sync),
    },
    {
      label: "Test",
      onclick: (event) => runTest(event, indexer, sync),
    },
    {
      label: "Disable",
      destructive: true,
      onclick: (event) => removeIndexer(event, indexer, sync),
    },
  ]);
}

// Restyle the cards in place so the grid does not redraw under the pointer.
function syncCards(view, selection) {
  view.querySelectorAll(".card.indexer").forEach((element) => {
    const picked = selection.has(element.dataset.id);
    element.classList.toggle("selected", picked);
    element.querySelector(".select-mark")?.classList.toggle("on", picked);
  });
}

function card(indexer, state, sync) {
  const selection = state.indexerSelection;
  const open = selection
    ? () => selection.toggle(indexer.id)
    : () => openConfigDialog(indexer, state, sync);
  const onclick = (event) => {
    if (!event.target.closest("a, button")) open();
  };
  const onkeydown = (event) => {
    if (event.key === "Enter" && event.target === event.currentTarget) {
      open();
    }
  };
  const picked = selection?.has(indexer.id);
  // As in iOS lists, the selection circle leads the row.
  const leading = selection ? selectMark(picked) : null;
  const menu = selection ? null : cardMenu(indexer, state, sync);
  return h(
    "article",
    {
      class: `card indexer${selection ? " selectable" : ""}${
        picked ? " selected" : ""
      }`,
      tabindex: "0",
      "data-id": indexer.id,
      onclick,
      onkeydown,
    },
    cardHeader(indexer, menu, leading),
    h("p", { class: "indexer-desc" }, indexer.description),
    indexer.last_error
      ? h("div", { class: "error-note" }, indexer.last_error)
      : null,
  );
}

// ---- configuration dialog ----

function searchButton(indexer, close) {
  if (!indexer.configured) return null;
  return button("Search", () => {
    close();
    location.hash = `search?tracker=${indexer.id}`;
  });
}

function saveHandler(context) {
  const { indexer, modal, message, getForm, mount, sync } = context;
  return async (event) => {
    await withBusy(event.currentTarget, async () => {
      message.hidden = true;
      try {
        await api.saveIndexerConfig(indexer.id, getForm().values());
        modal.close();
        sync.reload();
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

async function openConfigDialog(indexer, state, sync) {
  let form;
  let saved;
  const body = h("div", {});
  const message = h("div", { class: "form-error", hidden: true });
  const links = linkRows(indexerLinks(indexer, state));
  const save = button("Save", null, "primary");
  const snapshot = () => JSON.stringify(form.values());
  const syncSave = () => {
    save.disabled = snapshot() === saved;
  };
  const mount = (items) => {
    form = buildConfigForm(items);
    clear(body).append(...[form.form, links, form.docs].filter(Boolean));
    saved = snapshot();
    syncSave();
  };
  try {
    mount(await api.indexerConfig(indexer.id));
  } catch {
    return;
  }
  body.addEventListener("input", syncSave);
  body.addEventListener("change", syncSave);
  const modal = openModal({
    title: `Configure ${indexer.name}`,
    body: [body, message],
    footer: [searchButton(indexer, () => modal.close()), save].filter(Boolean),
  });
  const getForm = () => form;
  save.addEventListener(
    "click",
    saveHandler({ indexer, modal, message, getForm, mount, sync }),
  );
}
