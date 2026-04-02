import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import UpgradePanel from '../deck/UpgradePanel';

// Mock the API
vi.mock('../../api/decks', () => ({
  upgradeDeck: vi.fn(),
}));

import { upgradeDeck } from '../../api/decks';

const mockUpgradeDeck = vi.mocked(upgradeDeck);

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe('UpgradePanel', () => {
  beforeEach(() => {
    mockUpgradeDeck.mockReset();
  });

  it('renders form with budget input, focus dropdown, and submit button', () => {
    renderWithQuery(<UpgradePanel deckId={1} />);

    expect(screen.getByLabelText(/budget/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/focus category/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /get recommendations/i })).toBeInTheDocument();
  });

  it('renders section with correct aria-label', () => {
    renderWithQuery(<UpgradePanel deckId={1} />);
    expect(screen.getByRole('region', { name: /upgrade recommendations/i })).toBeInTheDocument();
  });

  it('sets default budget to 50', () => {
    renderWithQuery(<UpgradePanel deckId={1} />);
    const input = screen.getByLabelText(/budget/i) as HTMLInputElement;
    expect(input.value).toBe('50');
  });

  it('calls upgradeDeck on form submit', async () => {
    mockUpgradeDeck.mockResolvedValue({
      deck_id: 1,
      recommendations: [],
      total_cost: 0,
    });

    renderWithQuery(<UpgradePanel deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    await waitFor(() => {
      expect(mockUpgradeDeck).toHaveBeenCalledWith(1, { budget: 50 });
    });
  });

  it('shows empty state when no recommendations', async () => {
    mockUpgradeDeck.mockResolvedValue({
      deck_id: 1,
      recommendations: [],
      total_cost: 0,
    });

    renderWithQuery(<UpgradePanel deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    expect(await screen.findByText(/no upgrades found/i)).toBeInTheDocument();
  });

  it('displays recommendations after successful fetch', async () => {
    mockUpgradeDeck.mockResolvedValue({
      deck_id: 1,
      recommendations: [
        {
          card_out: 'Bad Card',
          card_in: 'Better Card',
          price_delta: 2.5,
          reason: 'Higher synergy',
          upgrade_score: 1.85,
        },
      ],
      total_cost: 2.5,
    });

    renderWithQuery(<UpgradePanel deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    expect(await screen.findByText('Bad Card')).toBeInTheDocument();
    expect(screen.getByText('Better Card')).toBeInTheDocument();
    expect(screen.getByText('+$2.50')).toBeInTheDocument();
    expect(screen.getByText('Higher synergy')).toBeInTheDocument();
    expect(screen.getByText('Total cost: $2.50')).toBeInTheDocument();
    expect(screen.getByText('1 recommendation')).toBeInTheDocument();
  });

  it('shows error message on failure', async () => {
    mockUpgradeDeck.mockRejectedValue(new Error('Server error'));

    renderWithQuery(<UpgradePanel deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    expect(await screen.findByText('Server error')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('passes focus when selected', async () => {
    mockUpgradeDeck.mockResolvedValue({
      deck_id: 1,
      recommendations: [],
      total_cost: 0,
    });

    renderWithQuery(<UpgradePanel deckId={1} />);

    const focusSelect = screen.getByLabelText(/focus category/i);
    fireEvent.change(focusSelect, { target: { value: 'card_draw' } });

    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    await waitFor(() => {
      expect(mockUpgradeDeck).toHaveBeenCalledWith(1, { budget: 50, focus: 'card_draw' });
    });
  });

  it('pluralizes recommendation count correctly', async () => {
    mockUpgradeDeck.mockResolvedValue({
      deck_id: 1,
      recommendations: [
        { card_out: 'A', card_in: 'B', price_delta: 1.0, reason: 'r1', upgrade_score: 1.0 },
        { card_out: 'C', card_in: 'D', price_delta: 2.0, reason: 'r2', upgrade_score: 0.5 },
      ],
      total_cost: 3.0,
    });

    renderWithQuery(<UpgradePanel deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    expect(await screen.findByText('2 recommendations')).toBeInTheDocument();
  });

  it('shows negative price delta with correct formatting', async () => {
    mockUpgradeDeck.mockResolvedValue({
      deck_id: 1,
      recommendations: [
        { card_out: 'Expensive', card_in: 'Cheap', price_delta: -3.0, reason: 'saves money', upgrade_score: 2.0 },
      ],
      total_cost: 0,
    });

    renderWithQuery(<UpgradePanel deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /get recommendations/i }));

    expect(await screen.findByText('$-3.00')).toBeInTheDocument();
  });
});
