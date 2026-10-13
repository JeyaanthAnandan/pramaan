import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { ready } from "./i18n";
import App from "./App";

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
