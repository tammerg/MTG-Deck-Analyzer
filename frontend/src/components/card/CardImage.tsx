import { useState } from 'react';
import { getImageUrl, type ImageSize } from '../../utils/scryfall';

interface CardImageProps {
  /** Scryfall card UUID (e.g. from image_url or a separate field) */
  scryfallId?: string;
  /** Fallback full image URL (e.g. stored image_url from backend) */
  imageUrl?: string | null;
  /** Display name of the card, used for alt text and fallback label */
  name: string;
  size?: ImageSize;
  className?: string;
}

/**
 * Lazy-loaded card image with skeleton placeholder and error fallback.
 *
 * Usage:
 *   <CardImage scryfallId="abc123..." name="Atraxa" size="normal" />
 *   <CardImage imageUrl={card.image_url} name={card.name} size="small" />
 */
export default function CardImage({
  scryfallId,
  imageUrl,
  name,
  size = 'normal',
  className = '',
}: CardImageProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  // Resolve URL: prefer explicit imageUrl, then construct from scryfallId
  const src =
    imageUrl ?? (scryfallId ? getImageUrl(scryfallId, size) : '');

  const handleLoad = () => setLoaded(true);
  const handleError = () => setError(true);

  return (
    <div
      className={[
        'relative aspect-[5/7] w-full overflow-hidden rounded-lg',
        className,
      ].join(' ')}
    >
      {/* Skeleton shown until image loads */}
      {!loaded && !error && (
        <div
          className="absolute inset-0 animate-pulse rounded-lg bg-[var(--color-surface-raised)]"
          aria-hidden="true"
        />
      )}

      {/* Error / no-image fallback */}
      {(error || !src) ? (
        <div className="flex h-full w-full flex-col items-center justify-center rounded-lg bg-[var(--color-surface-raised)] text-center">
          <span className="text-3xl" role="img" aria-label="Card back">&#9824;</span>
          <span className="mt-2 px-2 text-xs text-[var(--color-text-secondary)] leading-tight">
            {name}
          </span>
        </div>
      ) : (
        <img
          src={src}
          alt={`MTG card: ${name}`}
          loading="lazy"
          onLoad={handleLoad}
          onError={handleError}
          className={[
            'h-full w-full object-cover rounded-lg transition-opacity duration-300',
            loaded ? 'opacity-100' : 'opacity-0',
          ].join(' ')}
        />
      )}
    </div>
  );
}
