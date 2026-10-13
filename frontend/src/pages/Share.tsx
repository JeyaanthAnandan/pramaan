import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { AnimatedNumber, rise, stagger } from "@/lib/motion";
import { Logo, LangSwitch } from "@/components/Layout";
import { dateTime } from "@/lib/format";

const EXTRA_LABELS: Record<string, string> = {
  main_reducing_agent_of_precursor: "Main reducing agent (precursor)",
  mn_pct: "Mn, mass %",
  cr_pct: "Cr, mass %",
  ni_pct: "Ni, mass %",
  other_alloy_pct: "Other alloy elements, mass %",
  scrap_t_per_t_product: "Scrap used, t per t product",
  pre_consumer_scrap_pct: "Pre-consumer scrap, %",
};

/** M11: read-only buyer link. No login, summary only, no plant-level inputs. */
export default function Share() {
  const { token = "" } = useParams();
  const { t, i18n } = useTranslation();
  const q = useQuery({ queryKey: ["share", token], queryFn: () => api.getShare(token) });
  const s = q.data?.summary;
  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4">
          <Logo />
          <LangSwitch />
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        {q.isLoading && (
          <div className="space-y-4" aria-busy="true">
            <div className="skeleton h-12" />
            <div className="skeleton h-24" />
            <div className="skeleton h-64" />
          </div>
        )}
        {q.isError && <h1 className="mt-20 text-center text-base font-normal text-muted">{t("buyer.none")}</h1>}
        {s && (
          <>
            <div className="flex items-start gap-3 rounded-2xl border border-warn/40 bg-warnbg px-4 py-3 text-[14px] text-warnink">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
              <b>{s.banner}</b>
            </div>
            <div className="mt-6">
              <div className="eyebrow">{t("buyer.for_importer")}</div>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">{t("buyer.title")}</h1>
              <dl className="mt-3 grid gap-x-6 gap-y-1 text-[14px] sm:grid-cols-2">
                <div><dt className="inline text-muted">{t("buyer.operator")}: </dt><dd className="inline font-medium">{s.operator}, {s.country}</dd></div>
                <div><dt className="inline text-muted">{t("buyer.period")}: </dt><dd className="inline font-medium">{s.period}</dd></div>
                <div><dt className="inline text-muted">{t("buyer.generated")}: </dt><dd className="inline">{dateTime(s.generated_at, i18n.language)}</dd></div>
              </dl>
              <p className="mt-1 text-[12px] text-muted">{s.method}</p>
            </div>
            <motion.div className="mt-6 space-y-4" variants={stagger(0.1, 0.1)} initial="hidden" animate="show">
              {s.goods.map((g) => (
                <motion.section key={g.cn} variants={rise} className="card p-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <div>
                      <div className="eyebrow">CN {g.cn}</div>
                      <h2 className="font-semibold">{g.description}</h2>
                    </div>
                    <div className="text-right">
                      <div className="font-display text-4xl font-semibold">
                        <AnimatedNumber value={g.see_direct} format={(v) => v.toFixed((String(g.see_direct).split(".")[1] ?? "").length)} countUp />
                      </div>
                      <div className="text-[12px] text-muted">{t("buyer.see_direct")} · t CO2e / t</div>
                    </div>
                  </div>
                  <dl className="mt-4 grid gap-3 text-[13px] sm:grid-cols-2">
                    <div className="rounded-xl bg-sunk p-3">
                      <dt className="text-[11px] text-muted">{t("buyer.route")}</dt>
                      <dd>{g.production_route}</dd>
                    </div>
                    <div className="rounded-xl bg-sunk p-3">
                      <dt className="text-[11px] text-muted">{t("buyer.precursors")}</dt>
                      {g.precursor_data.map((p) => (
                        <dd key={p.precursor}>{p.precursor}: <b>{p.status}</b></dd>
                      ))}
                    </div>
                    <div className="rounded-xl bg-sunk p-3 sm:col-span-2">
                      <dt className="mb-1 text-[11px] text-muted">{t("buyer.extra")} (EC Guidance 5d, Table 3-1)</dt>
                      <dd className="num grid grid-cols-2 gap-x-6 gap-y-0.5 sm:grid-cols-3">
                        {Object.entries(g.extra_parameters).map(([k, v]) => (
                          <span key={k}><span className="text-muted">{EXTRA_LABELS[k] ?? k.replace(/_/g, " ")}:</span> {v ?? "—"}</span>
                        ))}
                      </dd>
                    </div>
                    <div className="rounded-xl bg-sunk p-3"><dt className="text-[11px] text-muted">SEFA</dt><dd className="num">{g.sefa} t CO2e/t</dd></div>
                    <div className="rounded-xl bg-sunk p-3"><dt className="text-[11px] text-muted">Default SEE 2026 (for comparison)</dt><dd className="num">{g.default_see_2026_for_comparison} t CO2e/t</dd></div>
                  </dl>
                </motion.section>
              ))}
            </motion.div>
            <p className="mt-8 text-center text-[12px] text-muted">Pramaan · {t("app.disclaimer")}</p>
          </>
        )}
      </main>
    </div>
  );
}
