/** Page-shaped placeholders while code or data loads (instead of a lone spinner). */
export function PageSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6" aria-busy="true" aria-label="Loading">
      <div className="skeleton h-5 w-40" />
      <div className="skeleton mt-3 h-9 w-2/3 max-w-lg" />
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <div className="skeleton h-32" />
        <div className="skeleton h-32" />
        <div className="skeleton h-32" />
      </div>
      <div className="skeleton mt-4 h-64" />
    </div>
  );
}

export function WorkspaceSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 pb-10 pt-6 sm:px-6" aria-busy="true" aria-label="Loading">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <div className="skeleton h-5 w-56" />
          <div className="skeleton mt-2 h-8 w-3/4 max-w-md" />
          <div className="skeleton mt-2 h-4 w-64" />
        </div>
        <div className="skeleton hidden h-[72px] w-64 sm:block" />
      </div>
      <div className="mt-6 grid grid-cols-3 gap-2">
        <div className="skeleton h-14" />
        <div className="skeleton h-14" />
        <div className="skeleton h-14" />
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="skeleton h-36" />
        <div className="skeleton h-36" />
        <div className="skeleton h-36" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="skeleton h-80" />
        <div className="skeleton h-80" />
      </div>
    </div>
  );
}
