'use client';

import React, { useEffect, useState } from 'react';
import {
  Calculator,
  IndianRupee,
  MapPin,
  Calendar,
  CreditCard,
  Fuel,
  Car,
  Filter,
  RefreshCw,
} from 'lucide-react';
import { State } from '@/types';
import { api } from '@/lib/api';
import { formatINR } from '@/lib/utils';

interface AffordabilityFormProps {
  onCalculate: (formData: any) => void;
  isLoading: boolean;
}

export default function AffordabilityForm({ onCalculate, isLoading }: AffordabilityFormProps) {
  const [states, setStates] = useState<State[]>([]);
  const [selectedState, setSelectedState] = useState<number>(1);
  const [monthlyIncome, setMonthlyIncome] = useState<number>(100000);
  const [existingEmis, setExistingEmis] = useState<number>(10000);
  const [downPayment, setDownPayment] = useState<number>(200000);
  const [tenureYears, setTenureYears] = useState<number>(5);
  const [cibilScore, setCibilScore] = useState<number>(750);
  const [commuteKm, setCommuteKm] = useState<number>(1000);

  // Preference filters
  const [selectedFuel, setSelectedFuel] = useState<string>('ALL');
  const [selectedBody, setSelectedBody] = useState<string>('ALL');
  const [selectedTransmission, setSelectedTransmission] = useState<string>('ALL');

  useEffect(() => {
    async function loadStates() {
      try {
        const res = await api.getStates();
        if (res && res.length > 0) {
          setStates(res);
          setSelectedState(res[0].id);
        }
      } catch (e) {
        console.error('Failed to load states:', e);
      }
    }
    loadStates();
  }, []);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    onCalculate({
      monthly_take_home_income: monthlyIncome,
      existing_monthly_emis: existingEmis,
      available_down_payment: downPayment,
      state_id: selectedState,
      desired_tenure_months: tenureYears * 12,
      cibil_score: cibilScore,
      monthly_commute_km: commuteKm,
      preferred_fuel_types: selectedFuel !== 'ALL' ? [selectedFuel] : undefined,
      preferred_body_types: selectedBody !== 'ALL' ? [selectedBody] : undefined,
      preferred_transmission: selectedTransmission !== 'ALL' ? [selectedTransmission] : undefined,
    });
  };

  // Trigger initial calculation once state is loaded
  useEffect(() => {
    if (selectedState) {
      handleSubmit();
    }
  }, [selectedState]);

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6"
    >
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
            <Calculator className="w-4 h-4" />
          </div>
          <h2 className="text-base font-bold text-white">Your Financial Profile</h2>
        </div>
        <span className="text-xs text-slate-400">India Retail Banking Standards</span>
      </div>

      {/* Row 1: Monthly Income & Existing EMIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-semibold text-slate-300 block mb-1.5 flex justify-between">
            <span>Monthly Take-Home Salary</span>
            <span className="text-emerald-400 font-bold">{formatINR(monthlyIncome)}</span>
          </label>
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500 text-sm font-bold">₹</span>
            <input
              type="number"
              min="15000"
              step="5000"
              value={monthlyIncome}
              onChange={(e) => setMonthlyIncome(Number(e.target.value))}
              className="w-full pl-8 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
              required
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-300 block mb-1.5 flex justify-between">
            <span>Existing Monthly EMIs (Home, Personal, etc.)</span>
            <span className="text-amber-400 font-bold">{formatINR(existingEmis)}</span>
          </label>
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500 text-sm font-bold">₹</span>
            <input
              type="number"
              min="0"
              step="1000"
              value={existingEmis}
              onChange={(e) => setExistingEmis(Number(e.target.value))}
              className="w-full pl-8 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Row 2: Down Payment & State/RTO Location */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-semibold text-slate-300 block mb-1.5 flex justify-between">
            <span>Available Down Payment Cash</span>
            <span className="text-teal-400 font-bold">{formatINR(downPayment)}</span>
          </label>
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500 text-sm font-bold">₹</span>
            <input
              type="number"
              min="0"
              step="10000"
              value={downPayment}
              onChange={(e) => setDownPayment(Number(e.target.value))}
              className="w-full pl-8 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-300 block mb-1.5">
            Registration State (for RTO Taxes)
          </label>
          <div className="relative">
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(Number(e.target.value))}
              className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors cursor-pointer"
            >
              {states.map((st) => (
                <option key={st.id} value={st.id}>
                  {st.name} ({st.code})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Row 3: Loan Tenure & CIBIL Score */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-semibold text-slate-300 block mb-1.5 flex justify-between">
            <span>Desired Loan Tenure</span>
            <span className="text-emerald-400 font-bold">{tenureYears} Years ({tenureYears * 12} mo)</span>
          </label>
          <div className="grid grid-cols-5 gap-2">
            {[3, 4, 5, 6, 7].map((yr) => (
              <button
                type="button"
                key={yr}
                onClick={() => setTenureYears(yr)}
                className={`py-2 rounded-xl text-xs font-semibold transition-colors ${
                  tenureYears === yr
                    ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                    : 'bg-slate-950 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700'
                }`}
              >
                {yr} Yrs
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-300 block mb-1.5 flex justify-between">
            <span>CIBIL Credit Score</span>
            <span className="text-emerald-400 font-bold">{cibilScore} ({cibilScore >= 750 ? 'Prime' : 'Standard'})</span>
          </label>
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: '800+ Super', val: 820 },
              { label: '750 - 799', val: 760 },
              { label: '700 - 749', val: 720 },
              { label: '< 700', val: 660 },
            ].map((tier) => (
              <button
                type="button"
                key={tier.val}
                onClick={() => setCibilScore(tier.val)}
                className={`py-2 px-1 rounded-xl text-[11px] font-semibold transition-colors ${
                  cibilScore === tier.val
                    ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                    : 'bg-slate-950 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700'
                }`}
              >
                {tier.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Row 4: Monthly Commute Slider */}
      <div>
        <div className="flex justify-between text-xs text-slate-300 font-semibold mb-2">
          <span>Expected Monthly Driving Distance (for Fuel TCO)</span>
          <span className="text-teal-400 font-bold">{commuteKm} km / month</span>
        </div>
        <input
          type="range"
          min="300"
          max="3000"
          step="100"
          value={commuteKm}
          onChange={(e) => setCommuteKm(Number(e.target.value))}
          className="w-full accent-emerald-400 bg-slate-950 h-2 rounded-lg cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-slate-500 mt-1">
          <span>300 km (Low City)</span>
          <span>1,000 km (Average)</span>
          <span>3,000 km (High Commute)</span>
        </div>
      </div>

      {/* Quick Filters: Fuel & Body Type */}
      <div className="border-t border-slate-800 pt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="text-[11px] font-semibold text-slate-400 block mb-1">Fuel Preference</label>
          <select
            value={selectedFuel}
            onChange={(e) => setSelectedFuel(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Fuel Types</option>
            <option value="Petrol">Petrol</option>
            <option value="Diesel">Diesel</option>
            <option value="CNG">CNG</option>
            <option value="Electric">Electric (EV)</option>
          </select>
        </div>

        <div>
          <label className="text-[11px] font-semibold text-slate-400 block mb-1">Body Type</label>
          <select
            value={selectedBody}
            onChange={(e) => setSelectedBody(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Body Types</option>
            <option value="SUV">SUV / Compact SUV</option>
            <option value="Hatchback">Hatchback</option>
            <option value="Sedan">Sedan</option>
          </select>
        </div>

        <div>
          <label className="text-[11px] font-semibold text-slate-400 block mb-1">Transmission</label>
          <select
            value={selectedTransmission}
            onChange={(e) => setSelectedTransmission(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">All Transmissions</option>
            <option value="Manual">Manual</option>
            <option value="Automatic">Automatic (AMT/AT/CVT/DCT)</option>
          </select>
        </div>
      </div>

      {/* Submit / Recalculate Button */}
      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 hover:from-emerald-400 hover:to-teal-300 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 transition-all duration-200 disabled:opacity-50"
      >
        {isLoading ? (
          <>
            <RefreshCw className="w-4 h-4 animate-spin" />
            Calculating On-Road & Affordability...
          </>
        ) : (
          <>
            <Calculator className="w-4 h-4" />
            Calculate My Affordable Cars
          </>
        )}
      </button>
    </form>
  );
}
