import { formatColorName } from '../../utils/format';

export interface SearchFilters {
  q: string;
  color_identity: string[];
  type: string;
}

interface CardSearchFiltersProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

const COLORS = ['W', 'U', 'B', 'R', 'G'];

const COLOR_BUTTON_STYLES: Record<string, string> = {
  W: 'bg-[var(--color-mana-w)] text-gray-900 border-gray-300',
  U: 'bg-[var(--color-mana-u)] text-white border-blue-400',
  B: 'bg-[#3d2b1f] text-white border-stone-500',
  R: 'bg-[var(--color-mana-r)] text-white border-red-400',
  G: 'bg-[var(--color-mana-g)] text-white border-green-400',
};

const CARD_TYPES = [
  '',
  'Creature',
  'Instant',
  'Sorcery',
  'Artifact',
  'Enchantment',
  'Planeswalker',
  'Land',
];

/**
 * Filter bar for card search: color identity toggles, type dropdown, text search.
 *
 * Usage:
 *   const [filters, setFilters] = useState<SearchFilters>({ q: '', color_identity: [], type: '' });
 *   <CardSearchFilters filters={filters} onChange={setFilters} />
 */
export default function CardSearchFilters({ filters, onChange }: CardSearchFiltersProps) {
  const toggleColor = (color: string) => {
    const next = filters.color_identity.includes(color)
      ? filters.color_identity.filter((c) => c !== color)
      : [...filters.color_identity, color];
    onChange({ ...filters, color_identity: next });
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-4 sm:flex-row sm:flex-wrap sm:items-center">
      {/* Text search */}
      <div className="flex-1 min-w-0">
        <label htmlFor="card-search-query" className="sr-only">
          Search cards
        </label>
        <input
          id="card-search-query"
          type="search"
          value={filters.q}
          onChange={(e) => onChange({ ...filters, q: e.target.value })}
          placeholder="Search cards..."
          className={[
            'w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
            'px-3 py-2 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)]',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
          ].join(' ')}
        />
      </div>

      {/* Color identity toggles */}
      <fieldset>
        <legend className="sr-only">Filter by color identity</legend>
        <div className="flex items-center gap-1" role="group" aria-label="Color identity filter">
          {COLORS.map((color) => {
            const isActive = filters.color_identity.includes(color);
            return (
              <button
                key={color}
                type="button"
                aria-pressed={isActive}
                aria-label={`Toggle ${formatColorName(color)}`}
                onClick={() => toggleColor(color)}
                className={[
                  'h-8 w-8 rounded-full border-2 text-xs font-bold transition-all',
                  isActive
                    ? COLOR_BUTTON_STYLES[color]
                    : 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border-[var(--color-border)] opacity-50',
                  'hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
                ].join(' ')}
              >
                {color}
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* Card type dropdown */}
      <div>
        <label htmlFor="card-type-filter" className="sr-only">
          Filter by card type
        </label>
        <select
          id="card-type-filter"
          value={filters.type}
          onChange={(e) => onChange({ ...filters, type: e.target.value })}
          className={[
            'rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
            'px-3 py-2 text-sm text-[var(--color-text-primary)]',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
          ].join(' ')}
        >
          {CARD_TYPES.map((type) => (
            <option key={type} value={type}>
              {type || 'All Types'}
            </option>
          ))}
        </select>
      </div>

      {/* Clear filters */}
      {(filters.q || filters.color_identity.length > 0 || filters.type) && (
        <button
          type="button"
          onClick={() => onChange({ q: '', color_identity: [], type: '' })}
          className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] underline"
        >
          Clear
        </button>
      )}
    </div>
  );
}
