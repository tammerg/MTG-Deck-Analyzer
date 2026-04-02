import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StrategyGuide from '../deck/StrategyGuide';
import type { DeckCardResponse, StrategyGuideResponse } from '../../api/types';

// Mock the hook
const mockGenerate = vi.fn();
const mockReset = vi.fn();

const mockHookReturn = {
  generate: mockGenerate,
  data: undefined as StrategyGuideResponse | undefined,
  isPending: false,
  error: null as Error | null,
  reset: mockReset,
};

vi.mock('../../hooks/useStrategyGuide', () => ({
  useStrategyGuide: () => mockHookReturn,
}));

const sampleGuide: StrategyGuideResponse = {
  archetype: 'combo',
  themes: ['graveyard', 'sacrifice'],
  win_paths: [
    {
      name: 'Combo: Infinite Damage',
      cards: ['Card A', 'Card B'],
      description: 'Deals infinite damage via loop',
      combo_id: 'c1',
    },
    {
      name: 'Direct Win',
      cards: ['Lab Maniac'],
      description: 'Win by drawing from empty library',
      combo_id: null,
    },
  ],
  game_phases: [
    {
      phase_name: 'Early Game',
      turn_range: 'Turns 1-3',
      priorities: ['Ramp', 'Card draw'],
      key_cards: ['Sol Ring', 'Arcane Signet'],
      description: 'Set up mana base.',
    },
    {
      phase_name: 'Mid Game',
      turn_range: 'Turns 4-7',
      priorities: ['Assemble combo'],
      key_cards: ['Tutor'],
      description: 'Find pieces.',
    },
    {
      phase_name: 'Late Game',
      turn_range: 'Turns 8+',
      priorities: ['Execute combo'],
      key_cards: ['Card A'],
      description: 'Win the game.',
    },
  ],
  hand_simulation: {
    total_simulations: 1000,
    keep_rate: 0.72,
    avg_land_count: 2.8,
    avg_ramp_count: 0.9,
    avg_cmc_in_hand: 2.5,
    sample_hands: [
      {
        cards: ['Land1', 'Land2', 'Land3', 'Spell1', 'Spell2', 'Spell3', 'Spell4'],
        land_count: 3,
        ramp_count: 0,
        avg_cmc: 3.0,
        has_win_enabler: false,
        keep_recommendation: true,
        reason: '3 lands (ideal)',
      },
    ],
    mulligan_advice: 'Excellent mana base. Most opening hands are keepable.',
  },
  key_synergies: [
    { card_a: 'Token Maker', card_b: 'Token Payoff', reason: 'shared tokens theme' },
  ],
  llm_narrative: null,
};

const sampleCards: DeckCardResponse[] = [
  {
    card_id: 1,
    quantity: 1,
    category: 'ramp',
    is_commander: false,
    card_name: 'Sol Ring',
    cmc: 1,
    colors: [],
    price: 2.0,
    mana_cost: '{1}',
    type_line: 'Artifact',
    oracle_text: '{T}: Add {C}{C}.',
    image_url: 'https://cards.scryfall.io/normal/front/a/b/ab123456-7890-abcd-ef12-345678901234.jpg',
  },
  {
    card_id: 2,
    quantity: 1,
    category: 'combo',
    is_commander: false,
    card_name: 'Card A',
    cmc: 3,
    colors: ['R'],
    price: 5.0,
    mana_cost: '{2}{R}',
    type_line: 'Creature',
    oracle_text: 'Combo piece.',
    image_url: 'https://cards.scryfall.io/normal/front/c/d/cd987654-3210-fedc-ba98-765432109876.jpg',
  },
  {
    card_id: 3,
    quantity: 1,
    category: 'utility',
    is_commander: false,
    card_name: 'Token Maker',
    cmc: 2,
    colors: ['W'],
    price: 1.0,
    mana_cost: '{1}{W}',
    type_line: 'Enchantment',
    oracle_text: 'Makes tokens.',
    image_url: null,
  },
];

describe('StrategyGuide', () => {
  beforeEach(() => {
    mockGenerate.mockClear();
    mockReset.mockClear();
    mockHookReturn.data = undefined;
    mockHookReturn.isPending = false;
    mockHookReturn.error = null;
  });

  it('renders Generate button initially', () => {
    render(<StrategyGuide deckId={1} />);
    expect(screen.getByRole('button', { name: /generate/i })).toBeInTheDocument();
  });

  it('calls generate on button click', () => {
    render(<StrategyGuide deckId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));
    expect(mockGenerate).toHaveBeenCalledTimes(1);
  });

  it('shows loading skeleton when pending', () => {
    mockHookReturn.isPending = true;
    render(<StrategyGuide deckId={1} />);
    expect(screen.getByText('Generating...')).toBeInTheDocument();
  });

  it('displays all sections after data loads', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Archetype badge
    expect(screen.getByText('combo')).toBeInTheDocument();

    // Theme badges
    expect(screen.getByText('graveyard')).toBeInTheDocument();
    expect(screen.getByText('sacrifice')).toBeInTheDocument();

    // Win conditions
    expect(screen.getByText('Win Conditions (2)')).toBeInTheDocument();

    // Game plan
    expect(screen.getByText('Game Plan')).toBeInTheDocument();
    expect(screen.getByText('Early Game')).toBeInTheDocument();

    // Hand simulation
    expect(screen.getByText('72%')).toBeInTheDocument();

    // Key synergies
    expect(screen.getByText('Key Synergies (1)')).toBeInTheDocument();
  });

  it('shows Regenerate button when data exists', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} />);
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument();
  });

  it('shows error message on failure', () => {
    mockHookReturn.error = new Error('Network error');
    render(<StrategyGuide deckId={1} />);
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('shows LLM fallback when no narrative', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} />);
    expect(screen.getByText('Enable an LLM provider for narrative analysis.')).toBeInTheDocument();
  });

  it('renders LLM narrative when present', () => {
    mockHookReturn.data = { ...sampleGuide, llm_narrative: 'This deck focuses on combo wins.' };
    render(<StrategyGuide deckId={1} />);
    expect(screen.getByText('This deck focuses on combo wins.')).toBeInTheDocument();
  });

  // ------- Card badge and lightbox tests -------

  it('renders card badge with thumbnail when image_url is available', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Sol Ring has image_url and appears in game phases key_cards
    const solRingBadges = screen.getAllByRole('button', { name: /view sol ring/i });
    expect(solRingBadges.length).toBeGreaterThan(0);

    // Badge should contain a thumbnail image
    const badge = solRingBadges[0];
    const img = badge.querySelector('img');
    expect(img).toBeTruthy();
    expect(img?.src).toContain('small');
  });

  it('renders text-only badge when card has no image_url', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Token Maker has null image_url, appears in key_synergies
    // It should render as a plain span, not a button
    const tokenMakers = screen.getAllByText('Token Maker');
    expect(tokenMakers.length).toBeGreaterThan(0);
    // The text-only badge is a span, not a button
    const textOnlyBadge = tokenMakers.find((el) => el.tagName === 'SPAN');
    expect(textOnlyBadge).toBeTruthy();
  });

  it('opens lightbox when card badge is clicked', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Click Sol Ring badge (in game phases)
    const solRingBadge = screen.getAllByRole('button', { name: /view sol ring/i })[0];
    fireEvent.click(solRingBadge);

    // Lightbox dialog should appear
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-label', 'Card image: Sol Ring');
  });

  it('closes lightbox on backdrop click', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Open lightbox
    const solRingBadge = screen.getAllByRole('button', { name: /view sol ring/i })[0];
    fireEvent.click(solRingBadge);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Click backdrop (the dialog overlay itself)
    fireEvent.click(screen.getByRole('dialog'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes lightbox on Escape key', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Open lightbox
    const solRingBadge = screen.getAllByRole('button', { name: /view sol ring/i })[0];
    fireEvent.click(solRingBadge);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Press Escape
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('displays card name in lightbox', () => {
    mockHookReturn.data = sampleGuide;
    render(<StrategyGuide deckId={1} cards={sampleCards} />);

    // Open lightbox for Card A (in win conditions after expanding)
    // First expand the win condition
    fireEvent.click(screen.getByText('Combo: Infinite Damage'));
    const cardABadge = screen.getAllByRole('button', { name: /view card a/i })[0];
    fireEvent.click(cardABadge);

    // Card name shown in lightbox
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-label', 'Card image: Card A');
    // Card name text below image
    expect(screen.getByText('Card A', { selector: 'p' })).toBeInTheDocument();
  });
});
