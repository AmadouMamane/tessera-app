/** Premium route-transition placeholder shared by every localized surface. */
export default function LocaleLoading() {
  return (
    <main
      aria-busy="true"
      className="flex min-h-full min-w-0 flex-col gap-3 bg-[var(--tessera-bg)] p-4 sm:p-6"
    >
      <div className="h-9 w-full max-w-md animate-pulse rounded-lg bg-[var(--tessera-surface)] motion-reduce:animate-none" />
      <div className="grid gap-3 md:grid-cols-3">
        {[0, 1, 2].map((item) => (
          <div
            key={item}
            className="h-28 animate-pulse rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] motion-reduce:animate-none"
          />
        ))}
      </div>
      <div className="min-h-[320px] flex-1 animate-pulse rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] motion-reduce:animate-none" />
    </main>
  );
}
