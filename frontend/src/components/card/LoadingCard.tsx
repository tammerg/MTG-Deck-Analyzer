/**
 * Skeleton placeholder matching standard MTG card dimensions (aspect-[5/7]).
 * Used during card data loading states.
 *
 * Usage:
 *   <LoadingCard />
 *   <LoadingCard showText={false} />
 */
interface LoadingCardProps {
  showText?: boolean;
}

export default function LoadingCard({ showText = true }: LoadingCardProps) {
  return (
    <div className="animate-pulse" aria-busy="true" aria-label="Loading card">
      {/* Card image skeleton */}
      <div className="aspect-[5/7] w-full rounded-lg bg-[var(--color-surface-raised)]" />
      {/* Card name skeleton */}
      {showText && (
        <div className="mt-2 space-y-1">
          <div className="h-3 w-3/4 rounded bg-[var(--color-surface-raised)]" />
          <div className="h-3 w-1/2 rounded bg-[var(--color-surface-raised)]" />
        </div>
      )}
    </div>
  );
}
