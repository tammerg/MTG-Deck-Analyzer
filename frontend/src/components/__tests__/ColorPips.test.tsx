import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ColorPips from '../card/ColorPips';

describe('ColorPips', () => {
  it('renders a pip for each color', () => {
    render(<ColorPips colors={['W', 'U', 'B']} />);
    expect(screen.getByLabelText('White')).toBeInTheDocument();
    expect(screen.getByLabelText('Blue')).toBeInTheDocument();
    expect(screen.getByLabelText('Black')).toBeInTheDocument();
  });

  it('renders colorless pip for empty array', () => {
    render(<ColorPips colors={[]} />);
    expect(screen.getByLabelText('Colorless')).toBeInTheDocument();
  });

  it('has a group aria-label listing all colors', () => {
    render(<ColorPips colors={['R', 'G']} />);
    expect(screen.getByLabelText('Colors: Red, Green')).toBeInTheDocument();
  });
});
