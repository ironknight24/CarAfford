'use client';

import React, { useState } from 'react';
import {
  Calendar,
  Fuel,
  ShieldCheck,
  Wrench,
  Percent,
  CircleDollarSign,
  TrendingDown,
  Info,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { TCOCalculationResponse, TCOPeriodBreakdown } from '@/types';
import { formatINR } from '@/lib/utils';

interface TCOBreakdownCardProps {
  tco: TCOCalculationResponse;
}

export default function TCOBreakdownCard({ tco }: TCOBreakdownCardProps) {
  const [activePeriod, setActivePeriod] = useState<'1_year' | '3_years' | '5_years'>('5_years');

  const period: TCOPeriodBreakdown = tco.periods[activePeriod];
  const driving = tco.driving_profile;
  const initial = tco.initial_cost;
  const financing = tco.financing;

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 rounded-2xl border border-slate-800 p-6 shadow-xl relative overflow-hidden space-y-6">
      {/* Glow Accent */}
      <div className="absolute top-0 left-1/3 w-72 h-72 bg-blue-500/5 rounded-full blur-3xl -z-0 pointer-events-none" />

      <div className="relative z-10 space-y-6">
        {/* Header with Period Selectors */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-400 flex items-center gap-1.5">
                <Layers className="w-4 h-4" />
                Total Cost of Ownership (TCO) Engine
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {tco.data_status || 'DEMO'} DATA
              </span>
            </div>
            <h2 className="text-xl font-bold text-white mt-0.5">
              {tco.vehicle ? `${tco.vehicle.variant_name || 'Vehicle'} Ownership Cost` : 'Vehicle Ownership Projection'}
            </h2>
          </div>

          {/* Period Selector Buttons */}
          <div className="flex items-center bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 self-start sm:self-auto">
            {(['1_year', '3_years', '5_years'] as const).map((key) => {
              const label = key === '1_year' ? '1 Year' : key === '3_years' ? '3 Years' : '5 Years';
              const isActive = activePeriod === key;
              return (
                <button
                  key={key}
                  onClick={() => setActivePeriod(key)}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Highlight Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Cash Outflow */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/40">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <CircleDollarSign className="w-4 h-4 text-blue-400" />
              <span>{period.label} Total Cash Outflow</span>
            </div>
            <div className="text-2xl font-bold text-white tracking-tight">
              {formatINR(period.total_cash_outflow)}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              Down Payment + Loan EMIs + All Operating Costs
            </div>
          </div>

          {/* Average Monthly Cost */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/40">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Calendar className="w-4 h-4 text-emerald-400" />
              <span>Avg. Monthly Ownership Cost</span>
            </div>
            <div className="text-2xl font-bold text-emerald-400 tracking-tight">
              {formatINR(period.average_monthly_cost)}
              <span className="text-xs text-slate-400 font-normal">/mo</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              Operating: {formatINR(period.average_monthly_operating_cost)}/mo
            </div>
          </div>

          {/* Operating Cost for Period */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/40">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Fuel className="w-4 h-4 text-amber-400" />
              <span>{period.label} Operating Expenses</span>
            </div>
            <div className="text-2xl font-bold text-amber-300 tracking-tight">
              {formatINR(period.total_operating_cost)}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              Fuel + Insurance Renewals + Maintenance
            </div>
          </div>

          {/* Estimated Economic Cost (Net of Resale) */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/40">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <TrendingDown className="w-4 h-4 text-purple-400" />
              <span>Estimated Economic Cost</span>
            </div>
            <div className="text-2xl font-bold text-purple-300 tracking-tight">
              {formatINR(period.estimated_economic_cost)}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              Est. Resale: {formatINR(period.estimated_resale_value)}
            </div>
          </div>
        </div>

        {/* Line Items Breakdown */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            {period.label} Cost Breakdown
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* 1. Fuel / Energy Cost */}
            <div className="bg-slate-800/30 rounded-xl p-3.5 border border-slate-700/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                  <Fuel className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-200">Fuel / Energy</div>
                  <div className="text-xs text-slate-400">
                    {driving.fuel_type} @ {driving.fuel_efficiency} {driving.efficiency_unit} (₹{driving.fuel_price_per_unit}/{driving.fuel_price_unit})
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-white">{formatINR(period.fuel_cost)}</div>
                <div className="text-[10px] text-slate-400">
                  {formatINR(tco.operating_costs.annual_fuel_cost)}/yr
                </div>
              </div>
            </div>

            {/* 2. Maintenance & Service */}
            <div className="bg-slate-800/30 rounded-xl p-3.5 border border-slate-700/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                  <Wrench className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-200">Routine Maintenance</div>
                  <div className="text-xs text-slate-400">
                    Scheduled services & consumables for {driving.annual_distance_km} km/yr
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-white">{formatINR(period.maintenance_cost)}</div>
                <div className="text-[10px] text-slate-400">
                  {formatINR(tco.operating_costs.annual_maintenance_cost)}/yr
                </div>
              </div>
            </div>

            {/* 3. Insurance Renewals */}
            <div className="bg-slate-800/30 rounded-xl p-3.5 border border-slate-700/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-200">Insurance Renewals</div>
                  <div className="text-xs text-slate-400">
                    {period.period_years > 1 ? `Years 2 to ${period.period_years} OD/TP renewals` : 'Included in on-road price'}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-white">
                  {parseFloat(String(period.insurance_cost)) > 0 ? formatINR(period.insurance_cost) : '₹0.00 (In On-Road)'}
                </div>
                <div className="text-[10px] text-slate-400">
                  Year 1 in purchase price
                </div>
              </div>
            </div>

            {/* 4. Financing Interest & Loan Fees */}
            <div className="bg-slate-800/30 rounded-xl p-3.5 border border-slate-700/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                  <Percent className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-200">Loan Interest & Fees</div>
                  <div className="text-xs text-slate-400">
                    {financing ? `${financing.bank_name || 'Bank'} @ ${financing.annual_interest_rate}% for ${financing.tenure_months} mo` : 'No loan interest (Cash purchase)'}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-white">
                  {formatINR(parseFloat(String(period.financing_interest)) + parseFloat(String(period.financing_fees)))}
                </div>
                <div className="text-[10px] text-slate-400">
                  Principal: {formatINR(period.loan_principal_paid)}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Expandable "How was this TCO calculated?" Math Explainer */}
        <details className="group bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden transition-all">
          <summary className="px-4 py-3 text-xs font-semibold text-slate-300 flex items-center justify-between cursor-pointer hover:text-white select-none">
            <span className="flex items-center gap-2">
              <span className="text-blue-400">📐</span>
              <span>How was this TCO calculated? (Math Explainer)</span>
            </span>
            <span className="text-slate-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="px-4 pb-4 pt-2 border-t border-slate-700/40 text-xs text-slate-300 space-y-3 font-sans">
            <div>
              <strong className="text-blue-300 block mb-0.5">1. Total Cash Outflow (Wallet Impact):</strong>
              <div className="bg-slate-900/80 p-2.5 rounded-lg font-mono text-[11px] text-blue-200 border border-slate-800">
                Cash Outflow = Down Payment + Loan Principal Paid + Interest & Fees + Fuel + Insurance + Maintenance + Parking/Tolls
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Reflects every single rupee leaving your bank account over the {period.label} ownership horizon.
              </p>
            </div>

            <div>
              <strong className="text-purple-300 block mb-0.5">2. True Economic Cost of Ownership:</strong>
              <div className="bg-slate-900/80 p-2.5 rounded-lg font-mono text-[11px] text-purple-200 border border-slate-800">
                Economic Cost = Total Cash Outflow - Estimated Vehicle Resale Value
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Accounts for vehicle equity recovery when selling the car at end of {period.label} based on Indian depreciation curves.
              </p>
            </div>
          </div>
        </details>

        {/* Disclaimer / Provenance Note */}
        <div className="flex items-start gap-2 text-xs text-slate-400 bg-slate-800/40 p-3 rounded-xl border border-slate-700/40">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <span>
            {tco.disclaimer ||
              'Total Cost of Ownership projections are calculated using Indian automotive benchmarks, standard fuel prices, and empirical depreciation models.'}
          </span>
        </div>
      </div>
    </div>
  );
}

