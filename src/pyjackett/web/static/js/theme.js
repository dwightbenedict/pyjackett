// Appearance preference: "system" follows the OS, otherwise light or dark.
const THEME_KEY = "jackett-theme";
export const THEMES = ["system", "light", "dark"];

export function storedTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return THEMES.includes(saved) ? saved : "system";
  } catch {
    return "system";
  }
}

function apply(theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export function setTheme(theme) {
  apply(theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* storage may be unavailable */
  }
}

export function setupTheme() {
  apply(storedTheme());
}
