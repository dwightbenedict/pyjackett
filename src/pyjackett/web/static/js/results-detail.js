// Dialog with every detail of one release and its actions as text buttons.
import { h } from "./dom.js";
import { formatBytes, timeAgo } from "./format.js";
import { linkRows } from "./link-rows.js";
import { openModal } from "./modal.js";
import { releaseActions } from "./results-actions.js";

const orDash = (value) => value ?? "—";

function detailRows(release) {
  return [
    ["Indexer", release.tracker],
    ["Category", release.category_desc],
    ["Size", release.size == null ? null : formatBytes(release.size)],
    ["Published", release.publish_date && timeAgo(release.publish_date)],
    ["Seeders", release.seeders],
    ["Leechers", release.peers],
    ["Grabs", release.grabs],
  ];
}

// The full value is on hover when it is truncated.
function detailCell([label, value]) {
  const text = String(orDash(value));
  return h(
    "div",
    { class: "cfg-cell detail-cell" },
    h("span", { class: "cfg-label" }, label),
    h("span", { class: "detail-value", title: text }, text),
  );
}

function detailGroup(release) {
  return h("div", { class: "cfg-group" }, detailRows(release).map(detailCell));
}

function actionButton({ label, run }, primary) {
  return h(
    "button",
    {
      class: `btn${primary ? " primary" : ""}`,
      type: "button",
      onclick: (event) => run(event.currentTarget),
    },
    label,
  );
}

function copyLinks(release) {
  const links = [];
  if (release.info_hash) {
    links.push({ label: "Info Hash", url: release.info_hash });
  }
  if (release.magnet_uri) {
    links.push({ label: "Magnet URI", url: release.magnet_uri });
  }
  return linkRows(links);
}

export function openResultDialog(release) {
  const actions = releaseActions(release);
  openModal({
    title: release.title,
    body: [
      detailGroup(release),
      copyLinks(release),
      release.details &&
        linkRows([{ label: "Open Details Page", href: release.details }]),
    ],
    footer: actions.map((action, index) => actionButton(action, index === 0)),
  });
}
