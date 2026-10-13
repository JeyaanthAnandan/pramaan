import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { lastProject, rememberProject } from "@/lib/session";
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
const Supplier = lazy(() => import("@/pages/Supplier"));
const Plan = lazy(() => import("@/pages/Plan"));
const Try = lazy(() => import("@/pages/Try"));
const Verify = lazy(() => import("@/pages/Verify"));

function Start() {
  const nav = useNavigate();
  useEffect(() => {
    api
      .demoLoad()
      .then((r) => {
        rememberProject(r.project_id);
        nav(`/p/${r.project_id}/capture`, { replace: true });
      })
      .catch(() => {
        // too many sample loads from this address, or offline: the visitor's earlier copy, else the landing page
        const prev = lastProject();
        nav(prev?.startsWith("demo-") ? `/p/${prev}/capture` : "/", { replace: true });
      });
  }, [nav]);
  return <Fallback />;
}

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

// A project page opened directly (a judge's link, a reload): its code and its data start now, alongside the
// app's own start-up, instead of one after another (the page's code, then the project, then its results).
const opened = /^\/p\/([^/]+)(?:\/(?:capture|gaps|report))?\/?$/.exec(window.location.pathname);
if (opened) {
  const pid = decodeURIComponent(opened[1]);
  void import("@/pages/Workspace");
  void qc.prefetchQuery({ queryKey: ["project", pid], queryFn: () => api.project(pid) });
  void qc.prefetchQuery({ queryKey: ["results", pid], queryFn: () => api.results(pid) });
  void qc.prefetchQuery({ queryKey: ["evidence", pid], queryFn: () => api.evidence(pid) });
}

const Fallback = PageSkeleton;

// pages fade in when you move between them, but not on the very first load: the first page should
// paint at once (it is the largest paint people and Lighthouse wait for)
let firstPageShown = false;

function Shell() {
  const loc = useLocation();
  const firstPage = !firstPageShown;
  useEffect(() => {
    firstPageShown = true;
  }, []);
  if (loc.pathname.startsWith("/share/") || loc.pathname.startsWith("/supplier/")) {
    // links for people outside the factory (the EU buyer, the rod supplier): no workspace chrome
    return (
      <Suspense fallback={<Fallback />}>
        <Routes>
          <Route path="/share/:token" element={<Share />} />
          <Route path="/supplier/:token" element={<Supplier />} />
        </Routes>
      </Suspense>
    );
  }
  // each top-level page fades in; moving between workspace steps is animated by the workspace itself
  const top = loc.pathname.startsWith("/p/") ? `/p/${loc.pathname.split("/")[2]}` : loc.pathname;
  return (
    <Layout>
      <Suspense fallback={<Fallback />}>
        <motion.div key={top} initial={firstPage ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/p/:pid" element={<Navigate to="report" replace />} />
          <Route path="/p/:pid/plan" element={<Plan />} />
          <Route path="/p/:pid/verify" element={<Verify />} />
          <Route path="/p/:pid/:step" element={<Workspace />} />
          <Route path="/start" element={<Start />} />
          <Route path="/proof" element={<Proof />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="/try" element={<Try />} />
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
