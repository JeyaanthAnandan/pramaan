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
  useEffect(() => {
    setZoom(false);
    if (!box || !zoomable) return;
    const id = window.setTimeout(() => setZoom(true), 650);
    return () => window.clearTimeout(id);
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
  const ring = { accent: "border-accent shadow-[0_0_0_9999px_rgb(0_0_0/0.28)]", good: "border-good shadow-[0_0_0_9999px_rgb(0_0_0/0.28)]", warn: "border-warn shadow-[0_0_0_9999px_rgb(0_0_0/0.28)]", bad: "border-bad shadow-[0_0_0_9999px_rgb(0_0_0/0.28)]" }[tone];

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-sunk" style={{ aspectRatio: aspect ? String(aspect) : "3 / 4" }}>
      <div className="absolute inset-0 transition-transform duration-[900ms] ease-[cubic-bezier(.2,.7,.2,1)]" style={{ transform, transformOrigin: "center" }}>
        <img src={src} alt={alt} className={`h-full w-full object-contain transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`} onLoad={() => setLoaded(true)} draggable={false} />
        {box && (
          <div
            className={`absolute rounded-[3px] border-2 ${ring} animate-pulsebox transition-opacity duration-500 ${loaded ? "opacity-100" : "opacity-0"}`}
            style={{ top: `${(box[0] - 4) / 10}%`, left: `${(box[1] - 5) / 10}%`, height: `${(box[2] - box[0] + 8) / 10}%`, width: `${(box[3] - box[1] + 10) / 10}%` }}
          />
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
