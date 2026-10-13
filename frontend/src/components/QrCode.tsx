import { useEffect, useState } from "react";

/** A QR code drawn as one SVG path (dark on white, so a phone camera reads it in dark mode too).
 *  The encoder loads on demand; nothing is sent anywhere. */
export function QrCode({ value, label, size = 128 }: { value: string; label: string; size?: number }) {
  const [cells, setCells] = useState<{ n: number; d: string } | null>(null);
  useEffect(() => {
    let alive = true;
    void import("qrcode-generator").then((m) => {
      const qr = m.default(0, "M");
      qr.addData(value);
      qr.make();
      const n = qr.getModuleCount();
      let d = "";
      for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`;
      if (alive) setCells({ n, d });
    });
    return () => {
      alive = false;
    };
  }, [value]);
  return (
    <div className="shrink-0 rounded-xl border border-line bg-white p-1.5" style={{ width: size, height: size }}>
      {cells ? (
        <svg viewBox={`-1 -1 ${cells.n + 2} ${cells.n + 2}`} role="img" aria-label={label} className="h-full w-full" shapeRendering="crispEdges">
          <path d={cells.d} fill="#14213d" />
        </svg>
      ) : (
        <div className="skeleton h-full w-full" aria-hidden />
      )}
    </div>
  );
}
