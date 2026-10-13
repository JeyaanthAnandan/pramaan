import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { ArrowRight, ClipboardList, Link2, ListChecks, PackageSearch, Send } from "lucide-react";
import { useProject } from "@/lib/project";
import { eur, inr } from "@/lib/format";
import { rise, stagger } from "@/lib/motion";
import { LetterDialog } from "./Lever";

type Tone = "bad" | "warn" | "good";
interface Step { key: string; tone: Tone; title: string; body: string; action?: JSX.Element }

const TONE: Record<Tone, string> = {
  bad: "border-bad/30 bg-badbg/60",
  warn: "border-warn/40 bg-warnbg/60",
  good: "border-good/30 bg-goodbg/60",
};
const ICON_TONE: Record<Tone, string> = { bad: "text-badink", warn: "text-warnink", good: "text-goodink" };

/** The one-glance answer to "what should I do next?": deterministic, from the result and the gaps. */
export function NextSteps() {
  const { t } = useTranslation();
  const { pid, result, bundle, refresh } = useProject();
  if (!result) return null;
  const fx = Number(result.money.fx.value);
  const steps: Step[] = [];
  const gaps = result.gaps;
  const setup = gaps.find((g) => g.group === "setup");
  if (setup) {
    steps.push({
      key: "setup",
      tone: setup.status === "red" ? "bad" : "warn",
      title: t(setup.status === "red" ? "next.setup_missing_t" : "next.setup_t"),
      body: t("next.setup_d", { lines: setup.params.lines || "—" }),
      action: (
        <Link to={`/p/${pid}/capture#setup`} className="btn-ghost h-9 min-h-0">
          <PackageSearch className="h-4 w-4" /> {t("next.setup_cta")}
        </Link>
      ),
    });
  }
  for (const p of result.processes.filter((x) => x.see)) {
    const b = p.buyer;
    if (p.precursor.data !== "ACTUAL_VERIFIED") {
      const share = (Number(result.calc_tree[`${p.id}.rod.contrib`]?.value ?? 0) / Number(p.see)) * 100;
      const parts = [
        b.supplier_saving_eur_t && Number(b.supplier_saving_eur_t) > 0
          ? t("next.supplier_saving", { saving: eur(b.supplier_saving_eur_t), annual: eur(b.supplier_saving_annual_eur), annual_inr: inr(Number(b.supplier_saving_annual_eur) * fx) })
          : t("next.supplier_share", { share: share.toFixed(0), precursor: p.precursor.name.toLowerCase() }),
      ];
      if (b.basis_2026 === "default") parts.push(t("next.use_default", { def: eur(b.default_eur_t), actual: eur(b.actual_eur_t) }));
      const req = bundle?.project.supplier_requests.find((s) => s.process_id === p.id);
      steps.push({
        key: `supplier-${p.id}`,
        tone: "bad",
        title: t("next.supplier_t", { supplier: p.precursor.supplier, product: p.name }),
        body: parts.join(" "),
        // the letter button stays mounted when the request status changes, so an open letter stays open
        action: (
          <div className="flex flex-wrap items-center gap-2">
            {req && req.status !== "not_requested" && (
              <a href={`#lever-${p.id}`} className="chip">
                <Send className="h-3 w-3" /> {t(`lever.st_${req.status}`)}
              </a>
            )}
            <LetterDialog processId={p.id} supplier={p.precursor.supplier} onSent={refresh} compact attention />
          </div>
        ),
      });
    } else if (Number(b.gap_vs_default_eur_t) > 0 && b.basis_2026 === "actual") {
      steps.push({
        key: `share-${p.id}`,
        tone: "good",
        title: t("next.share_t", { product: p.name }),
        body: t("next.share_d", { gap: eur(b.gap_vs_default_eur_t), annual: eur(b.annual_gap_eur), annual_inr: inr(Number(b.annual_gap_eur) * fx) }),
        action: (
          <a href="#buyer-link" className="btn-ghost h-9 min-h-0">
            <Link2 className="h-4 w-4" /> {t("next.share_cta")}
          </a>
        ),
      });
    }
  }
  const review = gaps.filter((g) => g.group === "review").length;
  if (review) {
    steps.push({
      key: "review",
      tone: "warn",
      title: t("next.review_t", { count: review }),
      body: t("next.review_d"),
      action: (
        <Link to={`/p/${pid}/gaps`} className="btn-ghost h-9 min-h-0">
          <ListChecks className="h-4 w-4" /> {t("next.review_cta")}
        </Link>
      ),
    });
  }
  const missing = gaps.filter((g) => g.status === "red" && !["precursor", "setup"].includes(g.group)).length;
  if (missing) {
    steps.push({
      key: "missing",
      tone: "bad",
      title: t("next.missing_t", { count: missing }),
      body: t("next.missing_d"),
      action: (
        <Link to={`/p/${pid}/gaps`} className="btn-ghost h-9 min-h-0">
          <ClipboardList className="h-4 w-4" /> {t("next.review_cta")}
        </Link>
      ),
    });
  }
  const order: Record<Tone, number> = { bad: 0, warn: 1, good: 2 };
  steps.sort((a, b) => order[a.tone] - order[b.tone]);
  if (!steps.length) return null;
  return (
    <section className="card p-4 sm:p-5" aria-labelledby="next-title">
      <h3 id="next-title" className="flex items-center gap-2 font-semibold">
        <ArrowRight className="h-4 w-4 text-accent" aria-hidden /> {t("next.title")}
      </h3>
      <motion.ol className="mt-3 space-y-2.5" variants={stagger(0.09, 0.15)} initial="hidden" animate="show">
        {steps.map((s, i) => (
          <motion.li key={s.key} variants={rise} className={`flex flex-wrap items-center gap-3 rounded-xl border p-3 ${TONE[s.tone]}`}>
            <div className="flex min-w-0 flex-[1_1_20rem] gap-3">
              <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-surface font-mono text-[12px] font-semibold shadow-card ${ICON_TONE[s.tone]}`} aria-hidden>
                {i + 1}
              </span>
              <div className="min-w-0">
                <div className="text-[14px] font-semibold leading-snug">{s.title}</div>
                <p className="mt-0.5 text-[13px] leading-relaxed text-ink2">{s.body}</p>
              </div>
            </div>
            {s.action && <div className="max-w-full shrink-0 sm:pl-2">{s.action}</div>}
          </motion.li>
        ))}
      </motion.ol>
    </section>
  );
}
