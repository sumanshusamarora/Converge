import Link from 'next/link';
import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Converge',
  description: 'Multi-repository coordination and governance tool',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <header className="site-header">
            <div className="site-header-inner">
              <Link href="/tasks" className="brand-block" aria-label="Converge home">
                <span className="brand-mark" aria-hidden="true" />
                <span className="brand-copy">
                  <strong>Converge</strong>
                  <small>Orchestration Console</small>
                </span>
              </Link>
              <nav className="top-nav" aria-label="Primary">
                <Link href="/tasks" className="top-nav-link">
                  Tasks
                </Link>
              </nav>
            </div>
          </header>
          <main className="page-wrap entry-animate">{children}</main>
        </div>
      </body>
    </html>
  );
}
