import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { rememberProject } from "@/lib/session";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig, motion } from "motion/react";
import { Layout } from "@/components/Layout";
import { ToastProvider } from "@/components/Toast";
import { PageSkeleton } from "@/components/Skeleton";
import { EASE } from "@/lib/motion";
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

const Fallback = PageSkeleton;

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
  // each top-level page fades in; moving between workspace steps is animated by the workspace itself
  const top = loc.pathname.startsWith("/p/") ? `/p/${loc.pathname.split("/")[2]}` : loc.pathname;
  return (
    <Layout>
      <Suspense fallback={<Fallback />}>
        <motion.div key={top} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
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
        </motion.div>
      </Suspense>
    </Layout>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <MotionConfig reducedMotion="user" transition={{ duration: 0.25, ease: EASE }}>
        <ToastProvider>
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Shell />
          </BrowserRouter>
        </ToastProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}
