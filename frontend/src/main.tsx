import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { ready } from "./i18n";
import App from "./App";

// A page's code that cannot be fetched shows the error boundary's "could not load". When the file is gone
// from the server (404: a newer version was published while this tab was open), load the app again, once,
// so the tab picks up the current version. A fetch that failed or was cancelled (offline, or the page is
// being left) is not reloaded: that would fight the visitor's own navigation.
window.addEventListener("vite:preloadError", (event) => {
  const msg = String((event as Event & { payload?: unknown }).payload ?? "");
  const url = /https?:\/\/[^\s'"]+?\.(?:js|css)\b/.exec(msg)?.[0];
  if (!url) return;
  void fetch(url, { method: "HEAD", cache: "no-store" })
    .then((r) => {
      if (r.status !== 404) return;
      const last = Number(sessionStorage.getItem("pramaan.reloaded") || 0);
      if (Date.now() - last < 10_000) return; // reloaded a moment ago: leave it to the error boundary
      sessionStorage.setItem("pramaan.reloaded", String(Date.now()));
      window.location.reload();
    })
    .catch(() => undefined); // offline, storage blocked or the page is going away
});

// render once the reader's language is in (English is bundled; others are a small chunk)
void ready.finally(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
