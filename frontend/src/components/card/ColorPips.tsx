import { formatColorName } from '../../utils/format';

interface ColorPipsProps {
  /** Array of single-letter WUBRG color codes */
  colors: string[];
  size?: 'sm' | 'md' | 'lg';
}

const COLOR_STYLES: Record<string, string> = {
  W: 'bg-[var(--color-mana-w)] border-gray-300',
  U: 'bg-[var(--color-mana-u)] border-blue-400',
  B: 'bg-[#3d2b1f] border-stone-600',
  R: 'bg-[var(--color-mana-r)] border-red-400',
  G: 'bg-[var(--color-mana-g)] border-green-400',
  C: 'bg-gray-500 border-gray-400',
};

const SIZE_STYLES = {
  sm: 'h-3 w-3',
  md: 'h-4 w-4',
  lg: 'h-5 w-5',
};

/**
 * Renders colored circle pips for each color in a WUBRG color array.
 *
 * Usage:
 *   <ColorPips colors={['W', 'U', 'B', 'G']} />
 *   <ColorPips colors={card.color_identity} size="lg" />
 */
export default function ColorPips({ colors, size = 'md' }: ColorPipsProps) {
  if (!colors || colors.length === 0) {
    return (
      <span
        className={`inline-block rounded-full border border-gray-500 bg-gray-500 ${SIZE_STYLES[size]}`}
        aria-label="Colorless"
        title="Colorless"
      />
    );
  }

  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`Colors: ${colors.map(formatColorName).join(', ')}`}
    >
      {colors.map((color) => (
        <span
          key={color}
          className={[
            'inline-block rounded-full border',
            COLOR_STYLES[color.toUpperCase()] ?? 'bg-gray-500 border-gray-400',
            SIZE_STYLES[size],
          ].join(' ')}
          title={formatColorName(color)}
          aria-label={formatColorName(color)}
        />
      ))}
    </span>
  );
}
