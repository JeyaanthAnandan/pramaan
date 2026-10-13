import { Component, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, RotateCw } from "lucide-react";

/** A page that cannot render (its code did not arrive, or a bug) shows what happened and a way on,
 *  instead of a blank screen. Keyed by the page, so moving to another page starts it fresh. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    return this.state.error ? <Crashed /> : this.props.children;
  }
}

function Crashed() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center" role="alert">
      <AlertTriangle className="mx-auto h-8 w-8 text-warn" aria-hidden />
      <h1 className="mt-3 text-xl font-semibold">{t("common.error")}</h1>
      <p className="mt-1 text-sm text-ink2">{t("common.crashed")}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <button className="btn-primary" onClick={() => window.location.reload()}>
          <RotateCw className="h-4 w-4" aria-hidden /> {t("common.reload")}
        </button>
        <a className="btn-ghost" href="/">
          {t("nav.home")}
        </a>
      </div>
    </div>
  );
}

/** Data that did not arrive (a server hiccup): say so and offer to try again, instead of an empty page. */
export function LoadError({ error, onRetry }: { error?: unknown; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="card mx-auto mt-8 max-w-lg p-6 text-center" role="alert">
      <AlertTriangle className="mx-auto h-6 w-6 text-warn" aria-hidden />
      <p className="mt-2 text-sm font-semibold">{t("common.error")}</p>
      {error instanceof Error && error.message && <p className="mt-1 text-[13px] text-muted">{error.message}</p>}
      <button className="btn-primary mt-4" onClick={onRetry}>
        <RotateCw className="h-4 w-4" aria-hidden /> {t("common.retry")}
      </button>
    </div>
  );
}
