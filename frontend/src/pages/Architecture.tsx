import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowDown, ArrowRight, Boxes, Calculator, ClipboardCheck, Cloud, Database, FileSearch, FileText, Hand, HardDrive, Inbox, MessageSquareText, ScanEye, ShieldCheck, Smartphone, Tags, Cpu, BookMarked, Activity, Gauge, Link2, MessagesSquare, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { Reveal } from "@/lib/motion";

const FLOW = [
  { k: "Intake", icon: Inbox, m: "code", c: "documents → run" },
  { k: "Classifier", icon: Tags, m: "gemini-3.8-flash", c: "{doc_id, doc_type, languages, period, confidence}" },
  { k: "ProductLines", icon: Boxes, m: "owner's lines, or gemini-3.8-flash proposal", c: "one line per exported CN code ← its steel input; every code checked against refdata; owner confirms" },
  { k: "Extractor", icon: FileSearch, m: "gemini-3.8-flash · high media resolution", c: "Field{field_key, value_text, value_num, unit, box_2d, page, label}" },
  { k: "Normalize", icon: Wand2, m: "code", c: "schema scope per field · one product line per single-material document · CN as dddd dd dd · salvaged numbers · ISO dates" },
  { k: "SecondReader", icon: ScanEye, m: "gemini-3.5-flash-lite · crop only", c: "{reading_value, reading_unit, agrees, delta, crossed_out}" },
  { k: "ControlChecks", icon: ClipboardCheck, m: "code", c: "Check{name, formula, inputs, result, tolerance, status}" },
  { k: "GapFinder", icon: ShieldCheck, m: "code → Calculator tool", c: "checklist per process + question per gap (EN/HI/TA/VI)" },
  { k: "Explainer", icon: MessageSquareText, m: "gemini-3.8-flash + numbers guard", c: "sections with page citations; no new numbers" },
  { k: "Reporter", icon: FileText, m: "code", c: "PDF · Excel · verifier pack · buyer summary" },
];

export default function Architecture() {
  const { t } = useTranslation();
  const h = useQuery({ queryKey: ["health"], queryFn: api.health });
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <span className="chip">ADK 2.x Workflow · google-genai Interactions API</span>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">{t("arch.title")}</h1>
      <p className="mt-2 max-w-3xl text-ink2">{t("arch.lead")}</p>

      <Reveal className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
        <section className="card p-5 sm:p-6">
          <div className="flex items-center gap-3 rounded-xl border border-line bg-sunk px-4 py-3 text-sm">
            <Smartphone className="h-5 w-5 text-muted" />
            <span><b>Phone / browser (PWA)</b> · camera capture · React + Vite · i18n EN/HI/TA/VI</span>
          </div>
          <div className="my-2 flex justify-center text-muted"><ArrowDown className="h-5 w-5" /></div>
          <div className="rounded-2xl border-2 border-accent/30 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Cloud className="h-4 w-4 text-accent" /> Cloud Run · pramaan · asia-southeast1 · FastAPI + SSE + SPA (one container)
            </div>
            <ol className="grid gap-2 sm:grid-cols-2">
              {FLOW.map((f, i) => (
                // each agent lights up in pipeline order, the way a run flows through the graph
                <li key={f.k} className="relative flex animate-nodeglow gap-3 rounded-xl border border-line bg-surface p-3" style={{ animationDelay: `${i}s` }}>
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent"><f.icon className="h-4 w-4" /></span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 text-sm font-semibold">
                      <span className="num text-muted">{i + 1}</span> {f.k}
                    </div>
                    <div className="font-mono text-[11px] text-accent">{f.m}</div>
                    <div className="mt-0.5 text-[12px] leading-snug text-ink2">{f.c}</div>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <div className="flex items-start gap-2 rounded-xl border border-warn/40 bg-warnbg p-3 text-[12px] text-warnink">
                <Hand className="mt-0.5 h-4 w-4 shrink-0" />
                <span><b>HumanReview</b> — SecondReader routes mismatches and hand-corrected figures here; amber values wait for a tap (PATCH /evidence), then a deterministic recalculation.</span>
              </div>
              <div className="flex items-start gap-2 rounded-xl border border-line bg-sunk p-3 text-[12px] text-ink2">
                <Calculator className="mt-0.5 h-4 w-4 shrink-0" />
                <span><b>Calculator</b> — Decimal CBAM engine exposed as an ADK FunctionTool. Every node → evidence, refdata or assumption. Golden tests G1–G8.</span>
              </div>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {[
                { icon: Link2, t: "Supplier link", d: "the rod supplier uploads its verified statement from a phone, no account; the same agents read only the new document; the line moves to verified data" },
                { icon: MessagesSquare, t: "Ask about this report", d: "engine facts (calc-tree ids) + guidance pages → gemini-3.8-flash → numbers guard; every number opens the Evidence Lens" },
                { icon: Gauge, t: "Plant pulse", d: "gas per tonne by month against the median month; hot months priced at the bill's own rate; all calculation nodes" },
              ].map((x) => (
                <div key={x.t} className="flex items-start gap-2 rounded-xl border border-line bg-surface p-3 text-[12px] text-ink2">
                  <x.icon className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <span><b className="text-ink">{x.t}</b> — {x.d}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
        <aside className="space-y-3">
          {[
            { icon: Cpu, t: "Gemini · Agent Platform", d: `${h.data?.models?.extraction ?? "gemini-3.8-flash"} · ${h.data?.models?.second_reader ?? "gemini-3.5-flash-lite"} · location ${h.data?.models?.gemini_location ?? "global"} · service account, no API keys` },
            { icon: Database, t: "Firestore (native)", d: "projects / documents / evidence / runs / results / share_links" },
            { icon: HardDrive, t: "Cloud Storage", d: "original photos (uniform access, private)" },
            { icon: BookMarked, t: "Reference data (in repo)", d: `${h.data?.refdata?.files?.length ?? 7} JSON files from official EC files · SHA-256 manifest · parser ${h.data?.refdata?.parser_version ?? ""}` },
            { icon: Activity, t: "Cloud Logging + Trace", d: "structured logs, run receipts, timings" },
          ].map((s) => (
            <div key={s.t} className="card card-hover flex gap-3 p-4">
              <s.icon className="mt-0.5 h-5 w-5 shrink-0 text-muted" />
              <div>
                <div className="text-sm font-semibold">{s.t}</div>
                <div className="text-[12px] leading-snug text-ink2">{s.d}</div>
              </div>
            </div>
          ))}
          <div className="card p-4 text-[12px] text-ink2">
            <div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-ink"><ArrowRight className="h-4 w-4" /> Rules</div>
            The LLM never does arithmetic · no hand-typed regulatory values · temperature/top_p/top_k never set · only Gemini 3.x models.
          </div>
        </aside>
      </Reveal>
    </div>
  );
}
