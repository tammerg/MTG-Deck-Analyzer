import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchCommanders } from '../../api/cards';
import type { CardResponse } from '../../api/types';
import CardImage from '../card/CardImage';
import { extractScryfallId } from '../../utils/scryfall';

interface CommanderSearchProps {
  onSelect: (card: CardResponse) => void;
  placeholder?: string;
  className?: string;
  /** Initial value for controlled usage */
  initialValue?: string;
}

/**
 * Autocomplete search input for Commander cards.
 * Debounces input by 300ms, shows a dropdown with card images.
 *
 * Usage:
 *   <CommanderSearch onSelect={(card) => setCommander(card)} />
 */
export default function CommanderSearch({
  onSelect,
  placeholder = 'Search for a commander...',
  className = '',
  initialValue = '',
}: CommanderSearchProps) {
  const [inputValue, setInputValue] = useState(initialValue);
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // 300ms debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(inputValue.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['commanders', debouncedQuery],
    queryFn: () => searchCommanders(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  });

  // Open dropdown when results arrive
  useEffect(() => {
    if (results.length > 0 && debouncedQuery.length >= 2) {
      setIsOpen(true);
      setActiveIndex(-1);
    } else {
      setIsOpen(false);
    }
  }, [results, debouncedQuery]);

  const handleSelect = useCallback(
    (card: CardResponse) => {
      setInputValue(card.name);
      setIsOpen(false);
      setActiveIndex(-1);
      onSelect(card);
    },
    [onSelect]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, results.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && results[activeIndex]) {
          handleSelect(results[activeIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setActiveIndex(-1);
        break;
    }
  };

  const handleBlur = (e: React.FocusEvent) => {
    // Close only if focus leaves the entire component
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsOpen(false);
    }
  };

  return (
    <div
      className={['relative', className].join(' ')}
      onBlur={handleBlur}
    >
      {/* Input */}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          aria-controls="commander-search-listbox"
          aria-activedescendant={activeIndex >= 0 ? `commander-option-${activeIndex}` : undefined}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (results.length > 0 && debouncedQuery.length >= 2) setIsOpen(true);
          }}
          placeholder={placeholder}
          className={[
            'w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
            'px-4 py-3 text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)]',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            'transition-colors',
          ].join(' ')}
        />
        {isFetching && (
          <span
            className="absolute right-3 top-1/2 -translate-y-1/2"
            aria-label="Searching..."
          >
            <svg
              className="h-4 w-4 animate-spin text-[var(--color-text-secondary)]"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
          </span>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && results.length > 0 && (
        <ul
          id="commander-search-listbox"
          ref={listRef}
          role="listbox"
          aria-label="Commander suggestions"
          className={[
            'absolute z-50 mt-1 w-full max-h-80 overflow-y-auto',
            'rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]',
            'shadow-2xl',
          ].join(' ')}
        >
          {results.map((card, index) => {
            const scryfallId = card.image_url
              ? extractScryfallId(card.image_url) ?? undefined
              : undefined;
            return (
              <li
                key={card.id}
                id={`commander-option-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                onMouseDown={(e) => {
                  e.preventDefault(); // prevent blur
                  handleSelect(card);
                }}
                onMouseEnter={() => setActiveIndex(index)}
                className={[
                  'flex items-center gap-3 px-3 py-2 cursor-pointer transition-colors',
                  index === activeIndex
                    ? 'bg-[var(--color-surface-raised)]'
                    : 'hover:bg-[var(--color-surface-raised)]',
                  index < results.length - 1
                    ? 'border-b border-[var(--color-border)]'
                    : '',
                ].join(' ')}
              >
                {/* Thumbnail */}
                <div className="h-10 w-7 flex-shrink-0">
                  <CardImage
                    scryfallId={scryfallId}
                    imageUrl={card.image_url}
                    name={card.name}
                    size="small"
                  />
                </div>
                {/* Info */}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">
                    {card.name}
                  </p>
                  <p className="text-xs text-[var(--color-text-secondary)] truncate">
                    {card.type_line}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
