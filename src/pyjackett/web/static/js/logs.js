// "Logs" tab: the most recent log lines, refreshed periodically.
import { api } from "./api.js";
import { clear, h } from "./dom.js";

const REFRESH_MILLISECONDS = 5000;

function line(entry) {
  const time = new Date(entry.When).toLocaleTimeString();
  return h(
    "div",
    { class: "log-line" },
    h("span", { class: "muted" }, time),
    h("span", { class: `lvl-${entry.Level}` }, entry.Level),
    h("span", {}, entry.Message),
  );
}

export async function renderLogs(view) {
  const list = h("div", { class: "card" });
  const auto = h("input", { type: "checkbox", checked: true });
  const draw = async () => {
    const entries = await api.logs();
    clear(list).append(
      entries.length
        ? entries.map(line)
        : h("div", { class: "empty" }, "No log entries yet."),
    );
  };
  clear(view).append(
    h(
      "div",
      { class: "view-head" },
      h("h1", {}, "Logs"),
      h(
        "div",
        { class: "toolbar" },
        h("label", { class: "switch" }, auto, "Auto refresh"),
        h(
          "button",
          { class: "btn", type: "button", onclick: draw },
          "Refresh",
        ),
      ),
    ),
    list,
  );
  await draw();
  const timer = setInterval(() => {
    if (!view.contains(list)) clearInterval(timer);
    else if (auto.checked) draw();
  }, REFRESH_MILLISECONDS);
}
