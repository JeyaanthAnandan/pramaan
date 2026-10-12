import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "@/lib/api";
import { Segmented, rise, stagger } from "@/lib/motion";

export default function Plan() {
  const { pid = "" } = useParams();
  const { t, i18n } = useTranslation();
  const [lang, setLang] = useState(i18n.language === "hi" ? "hi" : "en");
  const q = useQuery({ queryKey: ["plan", pid, lang], queryFn: () => api.plan(pid, lang) });
  const mp = q.data;
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <Link to={`/p/${pid}/report`} className="btn-quiet -ml-3">
          <ArrowLeft className="h-4 w-4" /> {t("common.back")}
        </Link>
        <Segmented
          role="toggle"
          className="ml-auto"
          value={lang}
          onChange={setLang}
          options={[
            { value: "en", label: "English" },
            { value: "hi", label: "हिंदी" },
          ]}
        />
        <button className="btn-ghost" onClick={() => window.print()}>
          <Printer className="h-4 w-4" /> {t("common.print")}
        </button>
      </div>
      {q.isLoading && (
        <div className="mt-6 space-y-3" aria-busy="true">
          <div className="skeleton h-10 w-2/3" />
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-24" />
          ))}
        </div>
      )}
      {mp && (
        <article className="mt-6">
          <span className="chip border-warn/40 bg-warnbg text-warnink">{mp.status}</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">{mp.title}</h1>
          <p className="mt-1 text-[13px] text-muted">{mp.basis}</p>
          <p className="mt-2 text-sm text-ink2">{mp.summary}</p>
          <motion.ol key={lang} className="mt-6 space-y-3" variants={stagger(0.04)} initial="hidden" animate="show">
            {mp.elements.map((e: any) => (
              <motion.li key={e.no} variants={rise} className={`card p-4 ${e.applicable ? "" : "border-dashed bg-sunk/40 shadow-none"}`}>
                <div className="flex gap-3">
                  <span className="num grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sunk text-[12px] font-semibold">{e.no}</span>
                  <div>
                    <h2 className={`text-[15px] font-semibold ${e.applicable ? "" : "text-ink2"}`}>{e.title}</h2>
                    <p className={`mt-1 text-[14px] leading-relaxed ${e.applicable ? "text-ink2" : "text-muted"}`}>{e.content}</p>
                  </div>
                </div>
              </motion.li>
            ))}
          </motion.ol>
        </article>
      )}
    </div>
  );
}
