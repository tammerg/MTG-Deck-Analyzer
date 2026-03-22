import { parseManaSymbols } from '../../utils/scryfall';
import ManaSymbol from './ManaSymbol';

interface ManaCostProps {
  /** Mana cost string with braces, e.g. '{2}{W}{U}' */
  cost: string;
  /** Size for each symbol in pixels */
  symbolSize?: number;
}

/**
 * Parses and renders a full mana cost as a row of ManaSymbol components.
 *
 * Usage:
 *   <ManaCost cost="{2}{W}{U}" />
 *   <ManaCost cost="{B}{G}" symbolSize={20} />
 */
export default function ManaCost({ cost, symbolSize = 16 }: ManaCostProps) {
  const symbols = parseManaSymbols(cost);

  if (symbols.length === 0) {
    return <span className="text-[var(--color-text-secondary)] text-xs">—</span>;
  }

  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`Mana cost: ${cost}`}
    >
      {symbols.map((symbol, index) => (
        <ManaSymbol key={`${symbol}-${index}`} symbol={symbol} size={symbolSize} />
      ))}
    </span>
  );
}
