import type { Metadata } from 'next';
import './globals.css';
import { AppProviders } from '@/features/providers';
import { AppHeader } from '@/components/layout/app-header';

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
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen font-sans">
        <AppProviders>
          <div className="flex min-h-screen flex-col">
            <AppHeader />
            <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">{children}</main>
            <footer className="border-t py-4 text-center text-xs text-muted-foreground">
              BharatContract AI · contract intelligence for Indian commercial contracts
            </footer>
          </div>
        </AppProviders>
      </body>
    </html>
  );
}
