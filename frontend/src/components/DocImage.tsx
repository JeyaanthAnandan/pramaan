import { useEffect, useState } from "react";
import { Maximize2, ZoomIn } from "lucide-react";

/** Source photo with the value's region highlighted. box = [ymin, xmin, ymax, xmax] in 0-1000.
 *  Starts on the full page, then glides into the region so the reader sees where it is. */
export function DocImage({ src, box, alt, zoomable = true, aspect, tone = "accent", label }: {
  src: string;
  box?: number[] | null;
  alt: string;
  zoomable?: boolean;
  aspect?: number;
  tone?: "accent" | "good" | "warn" | "bad";
  label?: string;
}) {
  const [zoom, setZoom] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [scan, setScan] = useState(0); // bumps once the zoom has landed: a reading beam sweeps the region
  useEffect(() => {
    setZoom(false);
    if (!box || !zoomable) return;
    const id = window.setTimeout(() => setZoom(true), 650);
    const id2 = window.setTimeout(() => setScan((x) => x + 1), 1500);
    return () => {
      window.clearTimeout(id);
      window.clearTimeout(id2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, box?.join(","), zoomable]);

  let transform = "none";
  if (zoom && box) {
    const [y0, x0, y1, x1] = box;
    const w = Math.max(x1 - x0, 20);
    const h = Math.max(y1 - y0, 20);
    const s = Math.min(3.2, Math.max(1.4, 380 / Math.max(w, h * 1.3)));
    const cx = (x0 + x1) / 2 / 10;
    const cy = (y0 + y1) / 2 / 10;
    // translate the region's centre to the middle, then scale around the middle
    transform = `scale(${s}) translate(${50 - cx}%, ${50 - cy}%)`;
  }
  const ring = { accent: "border-accent", good: "border-good", warn: "border-warn", bad: "border-bad" }[tone];
  const pad = box ? { t: (box[0] - 4) / 10, l: (box[1] - 5) / 10, b: (box[2] + 4) / 10, r: (box[3] + 5) / 10 } : null;

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-sunk" style={{ aspectRatio: aspect ? String(aspect) : "3 / 4" }}>
      <div className="absolute inset-0 transition-transform duration-[900ms] ease-[cubic-bezier(.2,.7,.2,1)]" style={{ transform, transformOrigin: "center" }}>
        <img src={src} alt={alt} className={`h-full w-full object-contain transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`} onLoad={() => setLoaded(true)} draggable={false} />
        {pad && (
          // one dim layer with a hole cut around the value (no seams, works inside the scaled layer)
          <div
            className={`pointer-events-none absolute inset-0 bg-black/30 transition-opacity duration-700 ${loaded && zoom ? "opacity-100" : "opacity-0"}`}
            style={{ clipPath: `polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${pad.l}% ${pad.t}%, ${pad.r}% ${pad.t}%, ${pad.r}% ${pad.b}%, ${pad.l}% ${pad.b}%, ${pad.l}% ${pad.t}%)` }}
            aria-hidden
          />
        )}
        {box && (
          <div
            className={`absolute overflow-hidden rounded-[3px] border-2 ${ring} transition-opacity duration-500 ${loaded ? "opacity-100" : "opacity-0"}`}
            style={{ top: `${(box[0] - 4) / 10}%`, left: `${(box[1] - 5) / 10}%`, height: `${(box[2] - box[0] + 8) / 10}%`, width: `${(box[3] - box[1] + 10) / 10}%` }}
          >
            {scan > 0 && <span key={scan} className="absolute inset-y-0 left-0 w-1/2 animate-scanx bg-gradient-to-r from-transparent via-white/70 to-transparent" aria-hidden />}
          </div>
        )}
      </div>
      {!loaded && <div className="absolute inset-0 animate-pulse bg-sunk" />}
      {box && zoomable && (
        <button type="button" onClick={() => setZoom((z) => !z)} className="absolute bottom-2 right-2 inline-flex min-h-[32px] items-center gap-1 rounded-lg bg-surface/90 px-2 text-xs font-medium text-ink shadow-card backdrop-blur hover:bg-surface" aria-label={zoom ? "Show full page" : "Zoom to value"}>
          {zoom ? <Maximize2 className="h-3.5 w-3.5" /> : <ZoomIn className="h-3.5 w-3.5" />}
          {zoom ? "Full page" : "Zoom"}
        </button>
      )}
      {label && <div className="absolute left-2 top-2 rounded-md bg-surface/90 px-2 py-0.5 text-[11px] font-medium text-ink2 shadow-card backdrop-blur">{label}</div>}
    </div>
  );
}

/** Exactly what the blind second reader saw: the padded crop only. */
export function CropView({ src, box, alt, imgAspect }: { src: string; box: number[]; alt: string; imgAspect: number }) {
  const [y0, x0, y1, x1] = box;
  const w = Math.max(x1 - x0, 1);
  const h = Math.max(y1 - y0, 1);
  return (
    <div className="relative w-full overflow-hidden rounded-lg border border-line bg-sunk" style={{ aspectRatio: `${(w / h) * imgAspect}` }}>
      <img
        src={src}
        alt={alt}
        className="absolute max-w-none"
        style={{ width: `${100000 / w}%`, height: `${100000 / h}%`, left: `${(-x0 * 100) / w}%`, top: `${(-y0 * 100) / h}%`, objectFit: "fill" }}
        draggable={false}
      />
    </div>
  );
}
