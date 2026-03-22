import { Outlet } from 'react-router';
import Header from './Header';
import Footer from './Footer';

/**
 * Root layout wrapper used by React Router.
 *
 * Usage (in router):
 *   { path: '/', element: <Layout />, children: [ ... ] }
 */
export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-surface)] text-[var(--color-text-primary)]">
      <Header />
      <main
        id="main-content"
        className="flex-1 mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8"
      >
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
