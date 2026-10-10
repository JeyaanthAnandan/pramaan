import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Doc, type Evidence, type ProjectBundle, type Result } from "./api";

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

export function ProjectProvider({ pid, children }: { pid: string; children: ReactNode }) {
  const qc = useQueryClient();
  const bundle = useQuery({ queryKey: ["project", pid], queryFn: () => api.project(pid), refetchInterval: (q) => (q.state.data?.running ? 2500 : false) });
  const hasResult = bundle.data?.has_result;
  const result = useQuery({ queryKey: ["results", pid], queryFn: () => api.results(pid), enabled: !!hasResult, staleTime: 10_000 });
  const evidence = useQuery({ queryKey: ["evidence", pid], queryFn: () => api.evidence(pid), enabled: !!hasResult, staleTime: 10_000 });

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
