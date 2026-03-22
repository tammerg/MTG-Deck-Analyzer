import type { CardResponse, DeckCardResponse } from '../../api/types';
import ManaCost from './ManaCost';
import PriceTag from './PriceTag';
import { getCategoryDisplayName, getCategoryColor } from '../../utils/categories';
import { truncate } from '../../utils/format';

type CardListItemProps =
  | { variant: 'card'; card: CardResponse; onClick?: (card: CardResponse) => void }
  | { variant: 'deck-card'; card: DeckCardResponse; budget?: number; onClick?: (card: DeckCardResponse) => void };

/**
 * A single row in a card list, supporting both search results and deck card views.
 *
 * Usage:
 *   <CardListItem variant="card" card={searchResult} onClick={handleSelect} />
 *   <CardListItem variant="deck-card" card={deckCard} budget={200} />
 */
export default function CardListItem(props: CardListItemProps) {
  // Resolve fields per variant to avoid discriminated union narrowing issues
  const name =
    props.variant === 'card'
      ? props.card.name
      : props.card.card_name;

  const typeLine = props.card.type_line;
  const manaCost = props.card.mana_cost;

  const price =
    props.variant === 'deck-card' ? props.card.price : null;
  const category =
    props.variant === 'deck-card' ? props.card.category : undefined;
  const quantity =
    props.variant === 'deck-card' ? props.card.quantity : undefined;
  const budget =
    props.variant === 'deck-card' ? props.budget : undefined;

  const handleClick = () => {
    if (props.variant === 'card') {
      props.onClick?.(props.card);
    } else {
      props.onClick?.(props.card);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  const hasClick = Boolean(props.onClick);

  return (
    <div
      role={hasClick ? 'button' : undefined}
      tabIndex={hasClick ? 0 : undefined}
      onClick={hasClick ? handleClick : undefined}
      onKeyDown={hasClick ? handleKeyDown : undefined}
      className={[
        'flex items-center gap-3 rounded-md px-3 py-2 text-sm',
        'border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
        hasClick
          ? 'cursor-pointer hover:bg-[var(--color-surface-raised)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] transition-colors'
          : '',
      ].join(' ')}
    >
      {/* Quantity badge (deck view) */}
      {quantity != null && (
        <span className="min-w-[24px] text-center font-bold text-[var(--color-text-secondary)]">
          {quantity}x
        </span>
      )}

      {/* Card name */}
      <span
        className="flex-1 font-medium text-[var(--color-text-primary)] truncate"
        title={name}
      >
        {truncate(name, 40)}
      </span>

      {/* Mana cost */}
      <span className="hidden sm:flex items-center">
        <ManaCost cost={manaCost} symbolSize={14} />
      </span>

      {/* Type line */}
      <span
        className="hidden md:block text-xs text-[var(--color-text-secondary)] w-36 truncate"
        title={typeLine}
      >
        {truncate(typeLine, 28)}
      </span>

      {/* Category badge */}
      {category && (
        <span
          className={[
            'hidden lg:inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
            getCategoryColor(category),
          ].join(' ')}
        >
          {getCategoryDisplayName(category)}
        </span>
      )}

      {/* Price */}
      <PriceTag price={price} budget={budget} />
    </div>
  );
}
