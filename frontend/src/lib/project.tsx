import { createContext, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, type Doc, type Evidence, type ProjectBundle, type Result } from "./api";
import { useToast } from "@/components/Toast";

interface Ctx {
  pid: string;
  bundle?: ProjectBundle;
  result?: Result;
  evidence?: Evidence[];
  docs: Record<string, Doc>;
  evById: Record<string, Evidence>;
  loading: boolean;
  error?: unknown;
  refresh: () => Promise<void>;
}

const ProjectCtx = createContext<Ctx | null>(null);

/** A supplier upload link is out and its statement has not been verified yet: keep an eye on it. */
const awaitingSupplier = (b?: ProjectBundle) => !!b?.project.supplier_requests.some((s) => s.link_token && (s.status === "requested" || s.status === "received"));

export function ProjectProvider({ pid, children }: { pid: string; children: ReactNode }) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const toast = useToast();
  const bundle = useQuery({
    queryKey: ["project", pid],
    queryFn: () => api.project(pid),
    staleTime: 2_000, // a bundle fetched at start-up (App.tsx) is used, not fetched again on mount
    // fast while agents run; slower while a supplier may upload (only while the tab is visible)
    refetchInterval: (q) => (q.state.data?.running ? 2500 : awaitingSupplier(q.state.data) ? 5000 : false),
  });
  const hasResult = bundle.data?.has_result;
  const result = useQuery({ queryKey: ["results", pid], queryFn: () => api.results(pid), enabled: !!hasResult, staleTime: 10_000 });
  const evidence = useQuery({ queryKey: ["evidence", pid], queryFn: () => api.evidence(pid), enabled: !!hasResult, staleTime: 10_000 });

  // a run started elsewhere (the supplier's upload link) finished, or a request moved on: reload the
  // report, and say it when the supplier's data is verified (the money on the report moves by itself)
  const seen = useRef<{ running: boolean; st: Record<string, string> } | null>(null);
  useEffect(() => {
    const b = bundle.data;
    if (!b) return;
    const st = Object.fromEntries(b.project.supplier_requests.map((s) => [s.process_id, s.status]));
    const before = seen.current;
    seen.current = { running: b.running, st };
    if (!before) return;
    const moved = b.project.supplier_requests.filter((s) => before.st[s.process_id] && before.st[s.process_id] !== s.status);
    if ((before.running && !b.running) || moved.length) {
      void Promise.all([qc.invalidateQueries({ queryKey: ["results", pid] }), qc.invalidateQueries({ queryKey: ["evidence", pid] })]);
    }
    moved.filter((s) => s.status === "verified").forEach((s) => toast(t("lever.toast_verified", { supplier: s.supplier })));
    moved.filter((s) => s.status === "received").forEach((s) => toast(t("lever.toast_received", { supplier: s.supplier }), "info"));
  }, [bundle.data, pid, qc, t, toast]);

  const value = useMemo<Ctx>(() => {
    const docs: Record<string, Doc> = {};
    bundle.data?.documents.forEach((d) => (docs[d.id] = d));
    const evById: Record<string, Evidence> = {};
    evidence.data?.forEach((e) => (evById[e.id] = e));
    return {
      pid,
      bundle: bundle.data,
      result: result.data,
      evidence: evidence.data,
      docs,
      evById,
      loading: bundle.isLoading || (!!hasResult && (result.isLoading || evidence.isLoading)),
      error: bundle.error || result.error || evidence.error,
      refresh: async () => {
        await Promise.all([qc.invalidateQueries({ queryKey: ["project", pid] }), qc.invalidateQueries({ queryKey: ["results", pid] }), qc.invalidateQueries({ queryKey: ["evidence", pid] })]);
      },
    };
  }, [pid, bundle.data, result.data, evidence.data, bundle.isLoading, result.isLoading, evidence.isLoading, bundle.error, result.error, evidence.error, hasResult, qc]);

  return <ProjectCtx.Provider value={value}>{children}</ProjectCtx.Provider>;
}

export function useProject(): Ctx {
  const c = useContext(ProjectCtx);
  if (!c) throw new Error("useProject outside ProjectProvider");
  return c;
}
