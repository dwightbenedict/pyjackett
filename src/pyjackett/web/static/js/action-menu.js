// An ellipsis button that opens a menu of secondary actions.
import { h } from "./dom.js";
import { symbol } from "./icons.js";

function menuItem({ label, onclick, destructive }, close) {
  return h(
    "button",
    {
      class: `status-option${destructive ? " destructive" : ""}`,
      type: "button",
      role: "menuitem",
      onclick: (event) => {
        event.stopPropagation();
        close();
        onclick(event);
      },
    },
    label,
  );
}

/** `items` is [{label, onclick, destructive}, ...]. */
export function actionMenu(label, items) {
  const toggle = h(
    "button",
    {
      class: "icon-btn",
      type: "button",
      title: label,
      "aria-label": label,
      "aria-haspopup": "menu",
      "aria-expanded": "false",
    },
    symbol("ellipsis"),
  );
  const menu = h("div", { class: "status-menu action-list", role: "menu" });
  menu.hidden = true;
  const root = h("div", { class: "action-menu" }, toggle, menu);
  const outside = (event) => !root.contains(event.target) && setOpen(false);
  const setOpen = (open) => {
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    const listen = open ? "addEventListener" : "removeEventListener";
    document[listen]("mousedown", outside);
  };
  menu.append(...items.map((item) => menuItem(item, () => setOpen(false))));
  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    setOpen(menu.hidden);
  });
  root.addEventListener(
    "keydown",
    (event) => event.key === "Escape" && setOpen(false),
  );
  return root;
}
