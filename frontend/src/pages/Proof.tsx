import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { BadgeCheck, CheckCircle2, FileWarning, Loader2, RotateCw, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Reveal } from "@/lib/motion";
import { dateTime } from "@/lib/format";

export default function Proof() {
  const { t, i18n } = useTranslation();
  const q = useQuery({ queryKey: ["golden-live"], queryFn: api.golden, staleTime: 0 });
  const d = q.data;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex-1">
          <span className="chip">EC Guidance No. 5d · 14 Aug 2026</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{t("proof.title")}</h1>
          <p className="mt-2 max-w-2xl text-ink2">{t("proof.lead")}</p>
        </div>
        {d && (
          <motion.div
            key={d.ran_at}
            initial={{ opacity: 0, scale: 1.25, rotate: -4 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 420, damping: 22 }}
            className={`flex items-center gap-3 rounded-2xl border px-4 py-3 ${d.all_pass ? "border-good/30 bg-goodbg text-goodink" : "border-bad/30 bg-badbg text-badink"}`}
          >
            <BadgeCheck className="h-8 w-8" />
            <div>
              <div className="text-lg font-semibold">{d.all_pass ? t("proof.all", { n: d.cases.length }) : t("proof.fail")}</div>
              <div className="text-[12px]">
                {t("proof.ran")} {d.duration_ms} ms · {dateTime(d.ran_at, i18n.language)}
              </div>
            </div>
            <button className="btn-quiet" onClick={() => q.refetch()} aria-label="Run again">
              {q.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
            </button>
          </motion.div>
        )}
      </div>
      {q.isLoading && (
        // one placeholder per case (8): the notes below stay below the fold instead of being pushed away when the cases arrive
        <div className="mt-8 space-y-4" aria-busy="true">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="skeleton h-48" />
          ))}
        </div>
      )}
      <div className="mt-8 space-y-4">
        {d?.cases.map((c: any, ci: number) => (
          <Reveal key={c.id} delay={Math.min(ci, 3) * 0.05}>
          <article className="card overflow-hidden">
            <header className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-ink text-sm font-semibold text-page">{c.id}</span>
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold">{c.title}</h2>
                <p className="text-[12px] text-muted">{c.source}</p>
              </div>
              {c.pass ? <CheckCircle2 key={d.ran_at} className="h-5 w-5 animate-pop text-good" style={{ animationDelay: `${0.25 + c.checks.length * 0.07}s` }} /> : <XCircle className="h-5 w-5 text-bad" />}
            </header>
            <div className="grid gap-4 p-5 lg:grid-cols-[1fr_1.4fr]">
              <dl className="space-y-1 text-[13px]">
                {Object.entries(c.inputs as Record<string, string>).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="w-36 shrink-0 text-muted">{k}</dt>
                    <dd className="text-ink2">{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label={c.title}>
                <table className="num w-full min-w-[420px] text-[13px]">
                  <thead className="text-left text-[11px] text-muted">
                    <tr>
                      <th className="pb-1.5 font-medium">{t("proof.case")}</th>
                      <th className="pb-1.5 text-right font-medium">{t("proof.expected")}</th>
                      <th className="pb-1.5 text-right font-medium">{t("proof.computed")}</th>
                      <th className="pb-1.5 text-right font-medium">{t("proof.tol")}</th>
                      <th className="pb-1.5">
                        <span className="sr-only">
                          {t("proof.pass")} / {t("proof.fail")}
                        </span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {c.checks.map((r: any, ri: number) => (
                      <tr key={r.key}>
                        <td className="py-1.5 pr-2">{r.label} <span className="text-muted">({r.unit})</span></td>
                        <td className="py-1.5 text-right font-semibold">{r.expected}</td>
                        <td className="py-1.5 text-right">{r.computed}</td>
                        <td className="py-1.5 text-right text-muted">±{r.tolerance}</td>
                        <td className="py-1.5 pl-2 text-right">
                          {/* each comparison ticks in turn: re-computed live, not a saved screenshot */}
                          {r.pass ? <CheckCircle2 key={d.ran_at} className="ml-auto h-4 w-4 animate-pop text-good" style={{ animationDelay: `${0.2 + ri * 0.07}s` }} aria-label={t("proof.pass")} /> : <XCircle className="ml-auto h-4 w-4 text-bad" aria-label={t("proof.fail")} />}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </article>
          </Reveal>
        ))}
      </div>
      <section className="mt-10 rounded-2xl border border-warn/40 bg-warnbg p-5">
        <h2 className="flex items-center gap-2 font-semibold text-warnink">
          <FileWarning className="h-5 w-5" /> {t("proof.notes_t")}
        </h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[14px] text-ink2">
          <li>{t("proof.n1")}</li>
          <li>{t("proof.n2")}</li>
          <li>{t("proof.n3")}</li>
        </ul>
      </section>
    </div>
  );
}
