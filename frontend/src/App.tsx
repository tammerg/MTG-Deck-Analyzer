import { Suspense, lazy } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router';
import Layout from './components/layout/Layout';
import ErrorBoundary from './components/ErrorBoundary';

// Lazy-load page components for code splitting
const HomePage = lazy(() => import('./pages/HomePage'));
const BuildPage = lazy(() => import('./pages/BuildPage'));
const DeckViewPage = lazy(() => import('./pages/DeckViewPage'));
const ResearchPage = lazy(() => import('./pages/ResearchPage'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function PageLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-busy="true">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--color-border)] border-t-[var(--color-accent)]" />
    </div>
  );
}

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
                    <Suspense fallback={<PageLoading />}>
                      <HomePage />
                    </Suspense>
                  </ErrorBoundary>
                }
              />
              <Route
                path="build"
                element={
                  <ErrorBoundary>
                    <Suspense fallback={<PageLoading />}>
                      <BuildPage />
                    </Suspense>
                  </ErrorBoundary>
                }
              />
              <Route
                path="deck/:deckId"
                element={
                  <ErrorBoundary>
                    <Suspense fallback={<PageLoading />}>
                      <DeckViewPage />
                    </Suspense>
                  </ErrorBoundary>
                }
              />
              <Route
                path="research"
                element={
                  <ErrorBoundary>
                    <Suspense fallback={<PageLoading />}>
                      <ResearchPage />
                    </Suspense>
                  </ErrorBoundary>
                }
              />
              <Route
                path="search"
                element={
                  <ErrorBoundary>
                    <Suspense fallback={<PageLoading />}>
                      <SearchPage />
                    </Suspense>
                  </ErrorBoundary>
                }
              />
              <Route
                path="settings"
                element={
                  <ErrorBoundary>
                    <Suspense fallback={<PageLoading />}>
                      <SettingsPage />
                    </Suspense>
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
