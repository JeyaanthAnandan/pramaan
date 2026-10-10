import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Loader2, Printer } from "lucide-react";
import { api } from "@/lib/api";

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
        <div className="ml-auto flex rounded-lg border border-line p-0.5">
          {["en", "hi"].map((l) => (
            <button key={l} className={`min-h-[36px] rounded-md px-3 text-[13px] ${lang === l ? "bg-sunk font-semibold" : "text-muted"}`} onClick={() => setLang(l)}>
              {l === "en" ? "English" : "हिंदी"}
            </button>
          ))}
        </div>
        <button className="btn-ghost" onClick={() => window.print()}>
          <Printer className="h-4 w-4" /> {t("common.print")}
        </button>
      </div>
      {q.isLoading && <Loader2 className="mx-auto mt-16 h-6 w-6 animate-spin text-muted" />}
      {mp && (
        <article className="mt-6">
          <span className="chip border-warn/40 bg-warnbg text-warnink">{mp.status}</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">{mp.title}</h1>
          <p className="mt-1 text-[13px] text-muted">{mp.basis}</p>
          <p className="mt-2 text-sm text-ink2">{mp.summary}</p>
          <ol className="mt-6 space-y-3">
            {mp.elements.map((e: any) => (
              <li key={e.no} className={`card p-4 ${e.applicable ? "" : "opacity-70"}`}>
                <div className="flex gap-3">
                  <span className="num grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sunk text-[12px] font-semibold">{e.no}</span>
                  <div>
                    <h2 className="text-[15px] font-semibold">{e.title}</h2>
                    <p className="mt-1 text-[14px] leading-relaxed text-ink2">{e.content}</p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </article>
      )}
    </div>
  );
}
