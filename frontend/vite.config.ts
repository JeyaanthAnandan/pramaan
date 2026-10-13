import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/** The fonts the first paint uses (the hero headline and lead, the logo) are found only once the
 *  stylesheet is parsed; preloading them lets the text settle in its own face sooner (the lead paragraph
 *  is the largest paint). Latin subsets only: other scripts load when a page needs them. */
function preloadFirstPaintFonts(): Plugin {
  const want = [/ibm-plex-sans-latin-400-normal-[^/]*\.woff2$/, /ibm-plex-sans-latin-600-normal-[^/]*\.woff2$/, /ibm-plex-sans-condensed-latin-600-normal-[^/]*\.woff2$/];
  return {
    name: "preload-first-paint-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        const files = Object.keys(ctx.bundle ?? {});
        return want.flatMap((re) => {
          const f = files.find((n) => re.test(n));
          return f ? [{ tag: "link", attrs: { rel: "preload", as: "font", type: "font/woff2", href: `/${f}`, crossorigin: "" }, injectTo: "head" as const }] : [];
        });
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), preloadFirstPaintFonts()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8080", ws: true }, "/healthz": "http://127.0.0.1:8080" },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
