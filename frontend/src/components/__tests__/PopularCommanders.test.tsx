import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PopularCommanders from '../research/PopularCommanders';
import type { PopularCommanderResponse } from '../../api/types';

// Mock the hook to avoid actual API calls
const mockCommanders: PopularCommanderResponse[] = [
  {
    card: {
      id: 1,
      oracle_id: 'atraxa-oracle',
      name: "Atraxa, Praetors' Voice",
      type_line: 'Legendary Creature - Phyrexian Angel Horror',
      oracle_text: 'Flying, vigilance, deathtouch, lifelink',
      mana_cost: '{G}{W}{U}{B}',
      cmc: 4,
      colors: ['W', 'U', 'B', 'G'],
      color_identity: ['W', 'U', 'B', 'G'],
      keywords: ['Flying', 'Vigilance'],
      edhrec_rank: 5,
      legal_commander: true,
      legal_brawl: true,
      updated_at: '2026-01-01',
      image_url: 'https://cards.scryfall.io/normal/front/a/b/abc.jpg',
    },
    num_decks: 5000,
  },
  {
    card: {
      id: 2,
      oracle_id: 'korvold-oracle',
      name: 'Korvold, Fae-Cursed King',
      type_line: 'Legendary Creature - Dragon Noble',
      oracle_text: 'Flying',
      mana_cost: '{2}{B}{R}{G}',
      cmc: 5,
      colors: ['B', 'R', 'G'],
      color_identity: ['B', 'R', 'G'],
      keywords: ['Flying'],
      edhrec_rank: 10,
      legal_commander: true,
      legal_brawl: false,
      updated_at: '2026-01-01',
      image_url: null,
    },
    num_decks: 3000,
  },
];

vi.mock('../../hooks/usePopularCommanders', () => ({
  usePopularCommanders: vi.fn(),
}));

import { usePopularCommanders } from '../../hooks/usePopularCommanders';
const mockUsePopularCommanders = vi.mocked(usePopularCommanders);

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('PopularCommanders', () => {
  it('renders commander cards when loaded', () => {
    mockUsePopularCommanders.mockReturnValue({
      commanders: mockCommanders,
      isLoading: false,
      error: null,
    });

    render(<PopularCommanders onSelect={vi.fn()} />, { wrapper });

    expect(screen.getByText('Popular Commanders')).toBeInTheDocument();
    expect(screen.getByText("Atraxa, Praetors' Voice")).toBeInTheDocument();
    expect(screen.getByText('Korvold, Fae-Cursed King')).toBeInTheDocument();
    expect(screen.getByText('5,000 decks')).toBeInTheDocument();
    expect(screen.getByText('3,000 decks')).toBeInTheDocument();
  });

  it('calls onSelect when a commander is clicked', () => {
    mockUsePopularCommanders.mockReturnValue({
      commanders: mockCommanders,
      isLoading: false,
      error: null,
    });

    const onSelect = vi.fn();
    render(<PopularCommanders onSelect={onSelect} />, { wrapper });

    fireEvent.click(screen.getByText("Atraxa, Praetors' Voice"));
    expect(onSelect).toHaveBeenCalledWith(mockCommanders[0].card);
  });

  it('renders loading skeletons', () => {
    mockUsePopularCommanders.mockReturnValue({
      commanders: [],
      isLoading: true,
      error: null,
    });

    render(<PopularCommanders onSelect={vi.fn()} />, { wrapper });

    expect(screen.getByText('Popular Commanders')).toBeInTheDocument();
    // 8 skeleton placeholders
    const section = screen.getByLabelText('Popular commanders');
    expect(section.querySelectorAll('.animate-pulse')).toHaveLength(8);
  });

  it('renders error message gracefully', () => {
    mockUsePopularCommanders.mockReturnValue({
      commanders: [],
      isLoading: false,
      error: new Error('Network error'),
    });

    render(<PopularCommanders onSelect={vi.fn()} />, { wrapper });

    expect(screen.getByText('Could not load popular commanders.')).toBeInTheDocument();
  });

  it('renders nothing when empty and not loading', () => {
    mockUsePopularCommanders.mockReturnValue({
      commanders: [],
      isLoading: false,
      error: null,
    });

    const { container } = render(<PopularCommanders onSelect={vi.fn()} />, { wrapper });
    expect(container.innerHTML).toBe('');
  });

  it('renders color identity pips', () => {
    mockUsePopularCommanders.mockReturnValue({
      commanders: mockCommanders,
      isLoading: false,
      error: null,
    });

    render(<PopularCommanders onSelect={vi.fn()} />, { wrapper });

    // Atraxa has WUBG
    const pips = screen.getAllByLabelText(/^[WUBRG]$/);
    expect(pips.length).toBeGreaterThanOrEqual(4);
  });
});
