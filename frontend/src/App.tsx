import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { rememberProject } from "@/lib/session";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Layout } from "@/components/Layout";
import Landing from "@/pages/Landing";

const Workspace = lazy(() => import("@/pages/Workspace"));
const Proof = lazy(() => import("@/pages/Proof"));
const Metrics = lazy(() => import("@/pages/Metrics"));
const Architecture = lazy(() => import("@/pages/Architecture"));
const Copilot = lazy(() => import("@/pages/Copilot"));
const Share = lazy(() => import("@/pages/Share"));
const Plan = lazy(() => import("@/pages/Plan"));

function Start() {
  const nav = useNavigate();
  useEffect(() => {
    api.demoLoad().then((r) => {
      rememberProject(r.project_id);
      nav(`/p/${r.project_id}/capture`, { replace: true });
    });
  }, [nav]);
  return <Fallback />;
}

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

function Fallback() {
  return (
    <div className="grid min-h-[40vh] place-items-center text-muted">
      <Loader2 className="h-6 w-6 animate-spin" />
    </div>
  );
}

function Shell() {
  const loc = useLocation();
  if (loc.pathname.startsWith("/share/")) {
    return (
      <Suspense fallback={<Fallback />}>
        <Routes>
          <Route path="/share/:token" element={<Share />} />
        </Routes>
      </Suspense>
    );
  }
  return (
    <Layout>
      <Suspense fallback={<Fallback />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/p/:pid" element={<Navigate to="report" replace />} />
          <Route path="/p/:pid/plan" element={<Plan />} />
          <Route path="/p/:pid/:step" element={<Workspace />} />
          <Route path="/start" element={<Start />} />
          <Route path="/proof" element={<Proof />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
