// Release actions offered by the detail dialog.
import { h } from "./dom.js";
import { copyLabel, copyWithConfirmation, withBusy } from "./feedback.js";

// A temporary link with `download` saves the file without leaving the page.
function downloadTorrent(url) {
  const link = h("a", { href: url, download: "" });
  document.body.append(link);
  link.click();
  link.remove();
}

async function sendToBlackhole(url) {
  await fetch(url);
}

function linkActions(release) {
  if (!release.link) {
    return [];
  }
  return [
    { label: "Download", run: () => downloadTorrent(release.link) },
    {
      label: copyLabel(),
      run: (button) => copyWithConfirmation(button, release.link),
    },
  ];
}

/** `[{label, run(button)}]` for what this release supports. */
export function releaseActions(release) {
  const actions = linkActions(release);
  if (release.magnet_uri) {
    actions.push({
      label: copyLabel("Copy Magnet"),
      run: (button) => copyWithConfirmation(button, release.magnet_uri),
    });
  }
  if (release.blackhole_link) {
    actions.push({
      label: "Blackhole",
      run: (button) =>
        withBusy(button, () => sendToBlackhole(release.blackhole_link)),
    });
  }
  return actions;
}
