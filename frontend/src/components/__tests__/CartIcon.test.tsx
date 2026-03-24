import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CartIcon } from '../icons/CartIcon';

describe('CartIcon', () => {
  it('renders an svg element', () => {
    const { container } = render(<CartIcon />);
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('passes className to the svg', () => {
    const { container } = render(<CartIcon className="h-4 w-4" />);
    const svg = container.querySelector('svg');
    // SVGElement.className is an SVGAnimatedString; use getAttribute for a plain string
    expect(svg?.getAttribute('class')).toContain('h-4');
    expect(svg?.getAttribute('class')).toContain('w-4');
  });

  it('has aria-hidden set', () => {
    const { container } = render(<CartIcon />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
  });

  it('renders cart circle and path elements', () => {
    const { container } = render(<CartIcon />);
    const circles = container.querySelectorAll('circle');
    const paths = container.querySelectorAll('path');
    expect(circles.length).toBe(2);
    expect(paths.length).toBeGreaterThanOrEqual(1);
  });
});
