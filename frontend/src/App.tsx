import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router';
import Layout from './components/layout/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import HomePage from './pages/HomePage';
import BuildPage from './pages/BuildPage';
import DeckViewPage from './pages/DeckViewPage';
import ResearchPage from './pages/ResearchPage';
import SearchPage from './pages/SearchPage';
import SettingsPage from './pages/SettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Root application component.
 * Provides QueryClient, routing, and a top-level error boundary.
 *
 * Routes:
 *   /              → HomePage
 *   /build         → BuildPage
 *   /deck/:deckId  → DeckViewPage
 *   /research      → ResearchPage
 *   /search        → SearchPage
 *   /settings      → SettingsPage
 */
export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route
                index
                element={
                  <ErrorBoundary>
                    <HomePage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="build"
                element={
                  <ErrorBoundary>
                    <BuildPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="deck/:deckId"
                element={
                  <ErrorBoundary>
                    <DeckViewPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="research"
                element={
                  <ErrorBoundary>
                    <ResearchPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="search"
                element={
                  <ErrorBoundary>
                    <SearchPage />
                  </ErrorBoundary>
                }
              />
              <Route
                path="settings"
                element={
                  <ErrorBoundary>
                    <SettingsPage />
                  </ErrorBoundary>
                }
              />
              {/* 404 fallback */}
              <Route
                path="*"
                element={
                  <div className="py-16 text-center">
                    <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
                      404 &mdash; Page Not Found
                    </h1>
                    <a href="/" className="mt-2 inline-block text-[var(--color-accent)] hover:underline">
                      Back to Home
                    </a>
                  </div>
                }
              />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
