import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StrategyGuide from '../deck/StrategyGuide';
import type { StrategyGuideResponse } from '../../api/types';

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
    render(<StrategyGuide deckId={1} />);

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
});
