import { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router';

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/build', label: 'Build' },
  { to: '/research', label: 'Research' },
  { to: '/search', label: 'Search' },
  { to: '/settings', label: 'Settings' },
];

/**
 * App header with sticky positioning and responsive navigation.
 *
 * On small screens (<640px), a hamburger button reveals a slide-down menu.
 * On larger screens, nav links render inline as usual.
 *
 * Keyboard accessibility:
 *   - Escape closes the mobile menu when it is open
 *   - Focus is trapped within the mobile menu when open
 */
export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const hamburgerRef = useRef<HTMLButtonElement>(null);

  // Close menu on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileOpen) {
        setMobileOpen(false);
        hamburgerRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [mobileOpen]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        mobileOpen &&
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        !hamburgerRef.current?.contains(e.target as Node)
      ) {
        setMobileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [mobileOpen]);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    [
      'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
      isActive
        ? 'bg-[var(--color-accent)] text-white'
        : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-text-primary)]',
      'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
    ].join(' ');

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-surface-alt)]">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo / App title */}
          <NavLink
            to="/"
            className="flex items-center gap-2 text-lg font-bold text-[var(--color-text-primary)] hover:text-[var(--color-accent)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] rounded"
          >
            <span className="text-2xl" role="img" aria-label="Spade card suit">
              &#9824;
            </span>
            <span className="hidden sm:inline">MTG Deck Builder</span>
          </NavLink>

          {/* Desktop navigation */}
          <nav aria-label="Main navigation" className="hidden sm:block">
            <ul className="flex items-center gap-1" role="list">
              {navItems.map(({ to, label }) => (
                <li key={to}>
                  <NavLink to={to} end={to === '/'} className={linkClass}>
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {/* Mobile hamburger button */}
          <button
            ref={hamburgerRef}
            type="button"
            aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={mobileOpen}
            aria-controls="mobile-menu"
            onClick={() => setMobileOpen((v) => !v)}
            className={[
              'sm:hidden rounded-md p-2 transition-colors',
              'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-text-primary)]',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            {mobileOpen ? (
              /* X icon */
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              /* Hamburger icon */
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu panel */}
      {mobileOpen && (
        <div
          id="mobile-menu"
          ref={menuRef}
          className="sm:hidden border-t border-[var(--color-border)] bg-[var(--color-surface-alt)]"
        >
          <nav aria-label="Mobile navigation">
            <ul className="space-y-0.5 px-4 py-3" role="list">
              {navItems.map(({ to, label }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={to === '/'}
                    className={linkClass}
                    onClick={() => setMobileOpen(false)}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      )}
    </header>
  );
}
