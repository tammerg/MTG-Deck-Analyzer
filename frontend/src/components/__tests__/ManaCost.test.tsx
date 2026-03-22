import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ManaCost from '../card/ManaCost';

describe('ManaCost', () => {
  it('renders mana symbols for a cost string', () => {
    render(<ManaCost cost="{2}{W}{U}" />);
    expect(screen.getByLabelText('Mana cost: {2}{W}{U}')).toBeInTheDocument();
  });

  it('renders a dash for empty cost', () => {
    render(<ManaCost cost="" />);
    // The em-dash fallback
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
