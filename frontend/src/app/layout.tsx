import type { Metadata } from 'next';
import { Fraunces, IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';
import { AppProviders } from '@/features/providers';
import { AppHeader } from '@/components/layout/app-header';

const fraunces = Fraunces({
  subsets: ['latin'],
  axes: ['SOFT', 'WONK'],
  variable: '--font-display',
  display: 'swap',
});

const plexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
  display: 'swap',
});

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'BharatContract AI',
    template: '%s · BharatContract AI',
  },
  description:
    'Legal contract intelligence — Indian-context risk-aware clause extraction and obligation tracking.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${fraunces.variable} ${plexSans.variable} ${plexMono.variable}`}
    >
      <body className="min-h-screen font-sans">
        <AppProviders>
          <div className="flex min-h-screen flex-col">
            <AppHeader />
            <main className="mx-auto w-full max-w-[1440px] flex-1 px-5 py-9 sm:px-8 lg:px-12">
              {children}
            </main>
            <footer className="border-t border-border">
              <div className="mx-auto flex max-w-[1440px] flex-col gap-2 px-5 py-7 text-xs text-muted-foreground sm:flex-row sm:items-baseline sm:justify-between sm:px-8 lg:px-12">
                <span className="font-display text-sm italic text-foreground/80">
                  BharatContract&nbsp;AI
                </span>
                <span>
                  Contract intelligence for Indian commercial contracts · informational only, not
                  legal advice
                </span>
              </div>
            </footer>
          </div>
        </AppProviders>
      </body>
    </html>
  );
}
