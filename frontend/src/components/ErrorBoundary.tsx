import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Optional custom fallback UI. If omitted, the default error UI is rendered. */
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * React error boundary that catches unhandled render errors and displays
 * a friendly fallback UI with a reload button.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <MyComponent />
 *   </ErrorBoundary>
 *
 *   // With custom fallback:
 *   <ErrorBoundary fallback={<p>Something went wrong.</p>}>
 *     <MyComponent />
 *   </ErrorBoundary>
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to console for development visibility. In production this would
    // be sent to a monitoring service.
    console.error('[ErrorBoundary] Uncaught render error:', error, info.componentStack);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  private handleDismiss = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback;
    }

    return (
      <div
        role="alert"
        aria-live="assertive"
        className="flex min-h-[50vh] flex-col items-center justify-center px-4 py-16 text-center"
      >
        {/* Error icon */}
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-red-950/60 border border-[var(--color-budget-over)]/40">
          <svg
            className="h-10 w-10 text-[var(--color-budget-over)]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
          Something went wrong
        </h1>
        <p className="mt-2 max-w-sm text-sm text-[var(--color-text-secondary)]">
          An unexpected error occurred. You can reload the page to try again, or
          dismiss this message to continue.
        </p>

        {/* Error detail (collapsed by default) */}
        {this.state.error && (
          <details className="mt-4 max-w-lg text-left">
            <summary className="cursor-pointer text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors">
              Error details
            </summary>
            <pre className="mt-2 overflow-auto rounded-md bg-[var(--color-surface-raised)] p-3 text-xs text-[var(--color-budget-over)] leading-relaxed">
              {this.state.error.message}
            </pre>
          </details>
        )}

        <div className="mt-8 flex items-center gap-4">
          <button
            type="button"
            onClick={this.handleReload}
            className={[
              'rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors',
              'bg-[var(--color-accent)] text-white',
              'hover:bg-[var(--color-accent-hover)]',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
            ].join(' ')}
          >
            Reload page
          </button>
          <button
            type="button"
            onClick={this.handleDismiss}
            className={[
              'rounded-lg px-5 py-2.5 text-sm font-medium transition-colors',
              'border border-[var(--color-border)] text-[var(--color-text-secondary)]',
              'hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-text-primary)]',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            Dismiss
          </button>
        </div>
      </div>
    );
  }
}
