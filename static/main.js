function syncNav() {
  document.querySelectorAll("nav a").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("href") === location.pathname);
  });
}

["htmx:pushedIntoHistory", "htmx:historyRestore", "popstate"].forEach((ev) =>
  window.addEventListener(ev, syncNav)
);
