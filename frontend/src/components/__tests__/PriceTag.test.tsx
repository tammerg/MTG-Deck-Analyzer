import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PriceTag from '../card/PriceTag';

describe('PriceTag', () => {
  it('renders a formatted price', () => {
    render(<PriceTag price={1.5} />);
    expect(screen.getByText('$1.50')).toBeInTheDocument();
  });

  it('renders N/A for null price', () => {
    render(<PriceTag price={null} />);
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('has an aria-label with the price', () => {
    render(<PriceTag price={2.99} />);
    expect(screen.getByLabelText('Price: $2.99')).toBeInTheDocument();
  });

  it('applies green class when under budget', () => {
    const { container } = render(<PriceTag price={50} budget={200} />);
    const span = container.querySelector('span');
    expect(span?.className).toContain('budget-ok');
  });

  it('applies yellow class when near budget', () => {
    const { container } = render(<PriceTag price={180} budget={200} />);
    const span = container.querySelector('span');
    expect(span?.className).toContain('budget-warn');
  });

  it('applies red class when over budget', () => {
    const { container } = render(<PriceTag price={250} budget={200} />);
    const span = container.querySelector('span');
    expect(span?.className).toContain('budget-over');
  });
});
