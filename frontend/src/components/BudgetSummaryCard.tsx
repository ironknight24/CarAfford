'use client';

import React from 'react';
import {
  Wallet,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Award,
  ShieldAlert,
  Info,
  Building2,
  ArrowRight,
} from 'lucide-react';
import { AffordabilityBudgetBreakdown, AffordabilityBudgetSummary } from '@/types';
import { formatINR, formatINRLakhs } from '@/lib/utils';

interface BudgetSummaryCardProps {
  summary: AffordabilityBudgetBreakdown | AffordabilityBudgetSummary | any;
}

export default function BudgetSummaryCard({ summary }: BudgetSummaryCardProps) {
  const maxOnRoad = parseFloat(
    summary.maximum_affordable_on_road_price || summary.max_affordable_on_road_price || '0'
  );
  const safeBudget = parseFloat(
    summary.recommended_safe_budget || summary.recommended_on_road_budget || '0'
  );
  const stretchBudget = parseFloat(
    summary.stretch_budget || summary.max_affordable_on_road_price || '0'
  );
  const emiBudget = parseFloat(
    summary.available_car_emi !== undefined
      ? summary.available_car_emi
      : summary.available_car_emi_budget || '0'
  );
  const maxLoan = parseFloat(
    summary.maximum_affordable_loan || summary.max_affordable_loan || '0'
  );
  const downPayment = parseFloat(
    summary.available_down_payment !== undefined ? summary.available_down_payment : '0'
  );
  const maxTotalEmi = parseFloat(
    summary.maximum_total_emi || summary.max_total_emi_allowed || '0'
  );
  const existingEmi = parseFloat(
    summary.existing_monthly_emi || summary.existing_monthly_emis || '0'
  );

  const assumptions = summary.applicable_financing_assumptions;
  const cibil = summary.cibil_score || (assumptions ? 750 : 750);
  const estRate = assumptions
    ? assumptions.interest_rate
    : summary.estimated_interest_rate || '8.75';
  const tenureMonths = assumptions
    ? assumptions.tenure_months
    : summary.tenure_months || 60;
  const profileName = summary.affordability_profile || 'BALANCED';
  const limitingFactor = summary.limiting_factor;
  const limitingReason = summary.limiting_factor_reason;
  const warnings: string[] = summary.warnings || [];
  const disclaimer =
    summary.disclaimer ||
    'Estimated financing capacity and affordability range calculated using personal finance heuristics and demo banking rates. This is not a bank loan sanction.';

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 rounded-2xl border border-slate-800 p-6 shadow-xl relative overflow-hidden space-y-6">
      {/* Background Accent */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -z-0 pointer-events-none" />

      <div className="relative z-10 space-y-6">
        {/* Header Title & Provenance */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <Award className="w-4 h-4" />
                Affordability Engine Capacity
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {summary.data_status || 'DEMO'} DATA
              </span>
            </div>
            <h2 className="text-xl font-bold text-white mt-0.5">Budget & Loan Capacity</h2>
          </div>

          <div className="flex items-center gap-2 flex-wrap text-xs text-slate-300">
            <span className="bg-slate-800/90 px-2.5 py-1 rounded-lg border border-slate-700/50">
              Profile: <strong className="text-emerald-400">{profileName}</strong>
            </span>
            <span className="bg-slate-800/90 px-2.5 py-1 rounded-lg border border-slate-700/50">
              Rate: <strong className="text-teal-300">{estRate}%</strong>
            </span>
            <span className="bg-slate-800/90 px-2.5 py-1 rounded-lg border border-slate-700/50">
              Tenure: <strong className="text-white">{tenureMonths} mo</strong>
            </span>
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
              Safe spending zone leaving headroom for fuel, maintenance & savings.
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
              Max capacity combining ₹{formatINR(downPayment)} cash + ₹{formatINR(maxLoan)} loan.
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
              Total EMI ceiling: ₹{formatINR(maxTotalEmi)} (Existing: ₹{formatINR(existingEmi)})
            </p>
          </div>
        </div>

        {/* Limiting Factor & Reason Banner */}
        {limitingReason && (
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3.5 flex items-start gap-3">
            <div className="w-6 h-6 rounded-lg bg-teal-500/10 text-teal-400 flex items-center justify-center shrink-0 mt-0.5">
              <Info className="w-4 h-4" />
            </div>
            <div className="space-y-0.5 text-xs">
              <span className="font-semibold text-white">
                Capacity Constraint:{' '}
                <strong className="text-teal-400">{limitingFactor || 'EMI Capacity'}</strong>
              </span>
              <p className="text-slate-400 leading-relaxed">{limitingReason}</p>
            </div>
          </div>
        )}

        {/* Warnings Banner */}
        {warnings.length > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 space-y-1">
            {warnings.map((warn, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-amber-300">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span>{warn}</span>
              </div>
            ))}
          </div>
        )}

        {/* Funding Composition Bar */}
        <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800/80">
          <div className="flex justify-between text-xs text-slate-400 mb-2">
            <span>Funding Breakdown:</span>
            <span>
              Down Payment: <strong className="text-white">{formatINR(downPayment)}</strong> + Max Loan: <strong className="text-white">{formatINR(maxLoan)}</strong>
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden flex">
            <div
              className="bg-teal-400 h-full transition-all duration-500"
              style={{
                width: `${Math.min(100, Math.max(10, (downPayment / (maxOnRoad || 1)) * 100))}%`,
              }}
              title="Down Payment"
            />
            <div
              className="bg-emerald-500 h-full transition-all duration-500 flex-1"
              title="Bank Loan"
            />
          </div>
          <div className="flex justify-between text-[11px] text-slate-400 mt-2">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-teal-400 inline-block" /> Down Payment Cash ({((downPayment / (maxOnRoad || 1)) * 100).toFixed(0)}%)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Estimated Bank Loan ({assumptions?.loan_product_name || 'Standard Loan'})
            </span>
          </div>
        </div>

        {/* Legal Disclaimer */}
        <div className="text-[11px] text-slate-400 border-t border-slate-800/80 pt-3 flex items-start gap-2 leading-normal">
          <ShieldAlert className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
          <span>{disclaimer}</span>
        </div>
      </div>
    </div>
  );
}
