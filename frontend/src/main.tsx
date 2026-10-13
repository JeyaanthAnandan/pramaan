import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { ready } from "./i18n";
import App from "./App";

// The first render waits (briefly) for the faces the text is set in: laid out in a fallback font first,
// a long title wraps differently once IBM Plex arrives and the page below it jumps (layout shift 0.99
// on a phone). The faces are preloaded, so this is usually a few hundred ms; never more than 400 ms.
const fonts = Promise.race([
  Promise.all(["400 16px 'IBM Plex Sans'", "600 16px 'IBM Plex Sans'", "600 16px 'IBM Plex Sans Condensed'", "500 12px 'IBM Plex Mono'"].map((f) => document.fonts.load(f))),
  new Promise((resolve) => setTimeout(resolve, 400)),
]).catch(() => undefined);

// render once the reader's language is in (English is bundled; others are a small chunk)
void Promise.allSettled([ready, fonts]).then(() => {
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
