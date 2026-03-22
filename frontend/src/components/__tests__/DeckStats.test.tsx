import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DeckStats from '../deck/DeckStats';

describe('DeckStats', () => {
  const defaultProps = {
    totalCards: 99,
    totalPrice: 198.5,
    averageCmc: 2.4,
    budgetTarget: 200,
    format: 'commander',
  };

  it('renders all stat values', () => {
    render(<DeckStats {...defaultProps} />);
    expect(screen.getByText('99')).toBeInTheDocument();
    expect(screen.getByText('$198.50')).toBeInTheDocument();
    expect(screen.getByText('2.40')).toBeInTheDocument();
  });

  it('shows under budget when within budget', () => {
    render(<DeckStats {...defaultProps} />);
    expect(screen.getByText('Under Budget')).toBeInTheDocument();
    expect(screen.getByText('+$1.50')).toBeInTheDocument();
  });

  it('shows over budget when exceeding budget', () => {
    render(<DeckStats {...defaultProps} totalPrice={250} />);
    expect(screen.getByText('Over Budget')).toBeInTheDocument();
    expect(screen.getByText('-$50.00')).toBeInTheDocument();
  });

  it('shows format when no budget target', () => {
    render(<DeckStats {...defaultProps} budgetTarget={null} />);
    expect(screen.getByText('commander')).toBeInTheDocument();
    expect(screen.getByText('Format')).toBeInTheDocument();
  });

  it('has an aria-label on the stats grid', () => {
    render(<DeckStats {...defaultProps} />);
    expect(screen.getByLabelText('Deck statistics')).toBeInTheDocument();
  });
});
