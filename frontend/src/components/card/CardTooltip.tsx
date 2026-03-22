import { useState, useRef, useCallback } from 'react';
import CardImage from './CardImage';
import { extractScryfallId } from '../../utils/scryfall';

interface CardTooltipProps {
  /** The card name for the alt text */
  cardName: string;
  /** The image URL from backend */
  imageUrl?: string | null;
  /** Oracle/rules text to show in tooltip */
  oracleText?: string;
  /** The trigger element(s) to wrap */
  children: React.ReactNode;
}

/**
 * Wraps its children and shows a floating card image + oracle text tooltip on hover.
 *
 * Usage:
 *   <CardTooltip cardName={card.name} imageUrl={card.image_url} oracleText={card.oracle_text}>
 *     <span>{card.name}</span>
 *   </CardTooltip>
 */
export default function CardTooltip({
  cardName,
  imageUrl,
  oracleText,
  children,
}: CardTooltipProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<'right' | 'left'>('right');
  const triggerRef = useRef<HTMLSpanElement>(null);
  const scryfallId = imageUrl ? extractScryfallId(imageUrl) ?? undefined : undefined;

  const handleMouseEnter = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      // If less than 240px to the right, flip to left
      setPosition(window.innerWidth - rect.right < 240 ? 'left' : 'right');
    }
    setVisible(true);
  }, []);

  const handleMouseLeave = useCallback(() => setVisible(false), []);

  return (
    <span
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
    >
      {children}

      {/* Tooltip */}
      {visible && (
        <div
          role="tooltip"
          className={[
            'pointer-events-none absolute z-50 w-56 rounded-lg shadow-2xl',
            'border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
            'top-0',
            position === 'right' ? 'left-full ml-2' : 'right-full mr-2',
          ].join(' ')}
        >
          <CardImage
            scryfallId={scryfallId}
            imageUrl={imageUrl}
            name={cardName}
            size="normal"
            className="rounded-t-lg"
          />
          {oracleText && (
            <div className="p-2">
              <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed line-clamp-5">
                {oracleText}
              </p>
            </div>
          )}
        </div>
      )}
    </span>
  );
}
