// DOM construction helpers.

const EMPTY = [undefined, null, false];

function isEmpty(value) {
  return EMPTY.includes(value);
}

function applyProp(element, key, value) {
  if (key.startsWith("on") && typeof value === "function") {
    element.addEventListener(key.slice(2).toLowerCase(), value);
  } else if (key === "class") {
    element.className = value;
  } else if (key === "dataset") {
    Object.assign(element.dataset, value);
  } else if (key in element && key !== "list") {
    element[key] = value;
  } else {
    element.setAttribute(key, value === true ? "" : value);
  }
}

function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (isEmpty(child)) {
      continue;
    }
    parent.append(
      child instanceof Node ? child : document.createTextNode(child),
    );
  }
}

/** Create an element: h("div", {class: "x", onclick: fn}, child, ...). */
export function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (!isEmpty(value)) {
      applyProp(element, key, value);
    }
  }
  append(element, children);
  return element;
}

export function clear(element) {
  element.replaceChildren();
  return element;
}
