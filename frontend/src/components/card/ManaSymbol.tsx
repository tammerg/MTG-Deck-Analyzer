import { getManaSymbolUrl } from '../../utils/scryfall';

interface ManaSymbolProps {
  /** Raw symbol string without braces, e.g. 'W', 'U', '2', 'B/G' */
  symbol: string;
  /** Size in pixels */
  size?: number;
}

/**
 * Renders a single mana symbol SVG from Scryfall's CDN.
 *
 * Usage:
 *   <ManaSymbol symbol="W" size={16} />
 *   <ManaSymbol symbol="B/G" />
 */
export default function ManaSymbol({ symbol, size = 16 }: ManaSymbolProps) {
  const url = getManaSymbolUrl(symbol);

  return (
    <img
      src={url}
      alt={`{${symbol}}`}
      width={size}
      height={size}
      className="inline-block"
      style={{ width: size, height: size }}
    />
  );
}
