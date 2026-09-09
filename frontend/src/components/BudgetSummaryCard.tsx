'use client';

import React from 'react';
import { Wallet, TrendingUp, AlertCircle, CheckCircle2, Award } from 'lucide-react';
import { AffordabilityBudgetSummary } from '@/types';
import { formatINR, formatINRLakhs } from '@/lib/utils';

interface BudgetSummaryCardProps {
  summary: AffordabilityBudgetSummary;
}

export default function BudgetSummaryCard({ summary }: BudgetSummaryCardProps) {
  const maxOnRoad = parseFloat(summary.max_affordable_on_road_price);
  const safeBudget = parseFloat(summary.recommended_on_road_budget);
  const emiBudget = parseFloat(summary.available_car_emi_budget);
  const maxLoan = parseFloat(summary.max_affordable_loan);
  const downPayment = parseFloat(summary.available_down_payment);

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 rounded-2xl border border-slate-800 p-6 shadow-xl relative overflow-hidden">
      {/* Background Accent */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -z-0 pointer-events-none" />

      <div className="relative z-10 space-y-6">
        {/* Header Title */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <Award className="w-4 h-4" />
              Your Financial Affordability Profile
            </span>
            <h2 className="text-xl font-bold text-white mt-0.5">Budget & Loan Capacity</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-700/50 w-fit">
            <span>CIBIL Score: <strong className="text-emerald-400">{summary.cibil_score}</strong></span>
            <span>•</span>
            <span>Est. Rate: <strong className="text-emerald-400">{summary.estimated_interest_rate}%</strong></span>
          </div>
        </div>

        {/* Big Numbers Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Safe Recommended Budget */}
          <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-4 relative">
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wide flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Recommended Safe Budget
            </span>
            <div className="text-2xl sm:text-3xl font-extrabold text-white mt-1">
              {formatINRLakhs(safeBudget)}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Keeps EMI & ownership expenses comfortably within safe limits.
            </p>
          </div>

          {/* Maximum On-Road Upper Limit */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-teal-400" />
              Maximum On-Road Limit
            </span>
            <div className="text-2xl sm:text-3xl font-extrabold text-white mt-1">
              {formatINRLakhs(maxOnRoad)}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Upper bank ceiling based on 40% FOIR limit.
            </p>
          </div>

          {/* Monthly Car EMI Capacity */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-1">
              <Wallet className="w-3.5 h-3.5 text-indigo-400" />
              Available Car EMI Budget
            </span>
            <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-1">
              {formatINR(emiBudget)} <span className="text-xs text-slate-400 font-normal">/ mo</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              After factoring in your existing ongoing EMIs.
            </p>
          </div>
        </div>

        {/* Budget Composition Bar */}
        <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800/80">
          <div className="flex justify-between text-xs text-slate-400 mb-2">
            <span>Funding Composition:</span>
            <span>
              Down Payment: <strong>{formatINR(downPayment)}</strong> + Max Loan: <strong>{formatINR(maxLoan)}</strong>
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden flex">
            <div
              className="bg-teal-400 h-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(10, (downPayment / (maxOnRoad || 1)) * 100))}%` }}
              title="Down Payment"
            />
            <div
              className="bg-emerald-500 h-full transition-all duration-500 flex-1"
              title="Bank Loan"
            />
          </div>
          <div className="flex justify-between text-[11px] text-slate-400 mt-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-teal-400 inline-block" /> Down Payment Cash
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Bank Car Loan ({summary.tenure_months} mo tenure)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
