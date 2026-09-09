import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'CarAfford - Indian Car Affordability, On-Road Price & EMI Intelligence',
  description:
    'Determine the cars in India you can realistically afford. Calculate accurate state RTO on-road prices, banking loan eligibility, and monthly Total Cost of Ownership.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-100 antialiased min-h-screen`}>
        {children}
      </body>
    </html>
  );
}
