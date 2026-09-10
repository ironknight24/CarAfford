'use client';

import Link from 'next/link';
import { Car, ShieldCheck, Calculator, Database } from 'lucide-react';

export default function Navbar() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            <Car className="w-5 h-5 text-slate-950" />
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1">
              Car<span className="text-emerald-400">Afford</span>
              <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ml-1">
                India
              </span>
            </span>
          </div>
        </Link>

        <nav className="flex items-center gap-6 text-sm font-medium">
          <Link
            href="/"
            className="text-slate-300 hover:text-emerald-400 transition-colors flex items-center gap-1.5"
          >
            <Calculator className="w-4 h-4" />
            Affordability Calculator
          </Link>
          <Link
            href="/explore"
            className="text-slate-300 hover:text-emerald-400 transition-colors flex items-center gap-1.5"
          >
            <Car className="w-4 h-4" />
            Explore Cars & On-Road
          </Link>
          <Link
            href="/admin"
            className="text-slate-300 hover:text-indigo-400 transition-colors flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/50"
          >
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            Data Quality & Admin
          </Link>
        </nav>
      </div>
    </header>
  );
}

