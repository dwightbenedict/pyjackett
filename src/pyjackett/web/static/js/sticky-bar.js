// Keep a filter bar stuck under the top bar: it slides away while scrolling
// down and returns as soon as the user scrolls back up.
export function hideOnScrollDown(bar) {
  let last = window.scrollY;
  const topbar = document.querySelector(".topbar");
  const onScroll = () => {
    if (!bar.isConnected) {
      window.removeEventListener("scroll", onScroll);
      return;
    }
    if (bar.closest("[hidden]")) return; // its tab is not on screen
    // The top bar wraps on narrow screens, so measure rather than assume.
    bar.style.setProperty("--topbar-h", `${topbar.offsetHeight}px`);
    const y = window.scrollY;
    if (Math.abs(y - last) < 6) return;
    bar.classList.toggle("away", y > last && y > 120);
    last = y;
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}
