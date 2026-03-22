import type { DeckCardResponse } from '../../api/types';
import CardImage from '../card/CardImage';
import ColorPips from '../card/ColorPips';
import { extractScryfallId } from '../../utils/scryfall';

interface CommanderBannerProps {
  commanders: DeckCardResponse[];
}

/**
 * Large hero banner showing commander card image(s), name, type line, and color pips.
 *
 * Usage:
 *   <CommanderBanner commanders={deck.commanders} />
 */
export default function CommanderBanner({ commanders }: CommanderBannerProps) {
  if (commanders.length === 0) return null;

  const allColors = Array.from(new Set(commanders.flatMap((c) => c.colors)));

  return (
    <section
      aria-label="Commander"
      className="flex flex-col items-center gap-6 py-8 sm:flex-row sm:justify-center"
    >
      {commanders.map((commander) => {
        const scryfallId = commander.image_url
          ? extractScryfallId(commander.image_url) ?? undefined
          : undefined;

        return (
          <div key={commander.card_id} className="flex flex-col items-center gap-3">
            {/* Card image */}
            <div className="w-48 sm:w-56">
              <CardImage
                scryfallId={scryfallId}
                imageUrl={commander.image_url}
                name={commander.card_name}
                size="normal"
              />
            </div>

            {/* Commander info */}
            <div className="text-center">
              <h2 className="text-lg font-bold text-[var(--color-text-primary)]">
                {commander.card_name}
              </h2>
              <p className="mt-0.5 text-sm text-[var(--color-text-secondary)]">
                {commander.type_line}
              </p>
            </div>
          </div>
        );
      })}

      {/* Color identity pips shown once for the full deck */}
      {commanders.length > 0 && (
        <div className="absolute top-4 right-4 sm:static sm:self-start sm:pt-2">
          <ColorPips colors={allColors} size="lg" />
        </div>
      )}
    </section>
  );
}
