export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--color-border)] bg-[var(--color-surface-alt)] py-6">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-2 sm:flex-row">
          <p className="text-sm text-[var(--color-text-secondary)]">
            MTG Commander Deck Builder &mdash; Powered by Scryfall &amp; AI
          </p>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Card data &copy; Scryfall. Not affiliated with Wizards of the Coast.
          </p>
        </div>
      </div>
    </footer>
  );
}
