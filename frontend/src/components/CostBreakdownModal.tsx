'use client';

import React from 'react';
import { X, Shield, FileText, Fuel, Wrench, CreditCard } from 'lucide-react';
import { OnRoadPriceBreakdown, OwnershipCostBreakdown } from '@/types';
import { formatINR, formatINRLakhs } from '@/lib/utils';

interface CostBreakdownModalProps {
  isOpen: boolean;
  onClose: () => void;
  carName: string;
  onRoadBreakdown?: OnRoadPriceBreakdown;
  ownershipCost?: OwnershipCostBreakdown;
}

export default function CostBreakdownModal({
  isOpen,
  onClose,
  carName,
  onRoadBreakdown,
  ownershipCost,
}: CostBreakdownModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FileText className="w-5 h-5 text-emerald-400" />
              Detailed Cost Breakdown
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">{carName}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm">
          {/* On-Road Price Line Items */}
          {onRoadBreakdown && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <CreditCard className="w-4 h-4 text-emerald-400" />
                On-Road Price Breakdown ({onRoadBreakdown.state_name}
                {onRoadBreakdown.is_bh_series ? ' - BH Series' : ''})
              </h4>
              <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-800/80 space-y-2.5">
                <div className="flex justify-between items-center text-slate-300">
                  <span>Ex-Showroom Price</span>
                  <span className="font-semibold text-white">{formatINR(onRoadBreakdown.ex_showroom_price)}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400 text-xs">
                  <span>State RTO Road Tax ({onRoadBreakdown.rto_road_tax_percent}%)</span>
                  <span className="text-slate-200">{formatINR(onRoadBreakdown.rto_road_tax)}</span>
                </div>
                {parseFloat(onRoadBreakdown.rto_cess) > 0 && (
                  <div className="flex justify-between items-center text-slate-400 text-xs">
                    <span>Road Safety / Infrastructure Cess</span>
                    <span className="text-slate-200">{formatINR(onRoadBreakdown.rto_cess)}</span>
                  </div>
                )}
                <div className="flex justify-between items-center text-slate-400 text-xs">
                  <span>Registration & Smart Card Fee</span>
                  <span className="text-slate-200">{formatINR(onRoadBreakdown.registration_charges)}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400 text-xs">
                  <span>FASTag Fee</span>
                  <span className="text-slate-200">{formatINR(onRoadBreakdown.fastag_charges)}</span>
                </div>
                {parseFloat(onRoadBreakdown.tcs_amount) > 0 && (
                  <div className="flex justify-between items-center text-amber-400/90 text-xs">
                    <span>1% TCS (Govt. Motor Vehicle Sec 206C)</span>
                    <span>{formatINR(onRoadBreakdown.tcs_amount)}</span>
                  </div>
                )}
                <div className="border-t border-slate-800 pt-2 flex justify-between items-center text-slate-300">
                  <span className="flex items-center gap-1">
                    <Shield className="w-3.5 h-3.5 text-teal-400" />
                    Insurance (1-Yr Own Damage + 3-Yr Third Party)
                  </span>
                  <span className="font-semibold text-white">{formatINR(onRoadBreakdown.insurance_total)}</span>
                </div>
                <div className="border-t border-slate-800/80 pt-2.5 flex justify-between items-center text-emerald-400 font-bold text-base">
                  <span>Total Estimated On-Road Price</span>
                  <span>{formatINR(onRoadBreakdown.on_road_price)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Monthly Total Cost of Ownership (TCO) */}
          {ownershipCost && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                <Fuel className="w-4 h-4 text-teal-400" />
                Monthly Running & Ownership Cost (TCO)
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                  <span className="text-[11px] text-slate-400 block">Monthly Loan EMI</span>
                  <span className="text-sm font-bold text-white mt-1 block">
                    {formatINR(ownershipCost.monthly_emi)}
                  </span>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                  <span className="text-[11px] text-slate-400 block">Estimated Fuel</span>
                  <span className="text-sm font-bold text-white mt-1 block">
                    {formatINR(ownershipCost.monthly_fuel_cost)}
                  </span>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                  <span className="text-[11px] text-slate-400 block">Amortized Insurance</span>
                  <span className="text-sm font-bold text-white mt-1 block">
                    {formatINR(ownershipCost.monthly_insurance_cost)}
                  </span>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                  <span className="text-[11px] text-slate-400 block">Maintenance Reserve</span>
                  <span className="text-sm font-bold text-white mt-1 block">
                    {formatINR(ownershipCost.monthly_maintenance_cost)}
                  </span>
                </div>
              </div>
              <div className="mt-3 bg-emerald-950/30 border border-emerald-500/20 p-3.5 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-emerald-300 block">
                    Total Monthly Cost of Ownership (TCO)
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Accounts for {ownershipCost.tco_percentage_of_income}% of your monthly take-home pay
                  </span>
                </div>
                <span className="text-lg font-bold text-emerald-400">
                  {formatINR(ownershipCost.total_monthly_tco)} / mo
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
