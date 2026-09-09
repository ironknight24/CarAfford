'use client';

import React, { useState } from 'react';
import {
  Car,
  ShieldCheck,
  Zap,
  TrendingUp,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import Navbar from '@/components/Navbar';
import AffordabilityForm from '@/components/AffordabilityForm';
import BudgetSummaryCard from '@/components/BudgetSummaryCard';
import CarRecommendationCard from '@/components/CarRecommendationCard';
import { AffordabilityBudgetBreakdown, RecommendationResponse } from '@/types';
import { api } from '@/lib/api';

export default function HomePage() {
  const [affordabilityData, setAffordabilityData] = useState<AffordabilityBudgetBreakdown | null>(null);
  const [recommendationData, setRecommendationData] = useState<RecommendationResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleCalculate = async (formData: any) => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [affordRes, recRes] = await Promise.allSettled([
        api.calculateAffordability({
          monthly_take_home_income: formData.monthly_take_home_income,
          existing_monthly_emi: formData.existing_monthly_emis || formData.existing_monthly_emi || 0,
          available_down_payment: formData.available_down_payment || 0,
          state_id: formData.state_id,
          city_id: formData.city_id,
          rto_id: formData.rto_id,
          credit_score: formData.cibil_score || formData.credit_score || 750,
          preferred_loan_tenure_months: formData.desired_tenure_months || formData.preferred_loan_tenure_months || 60,
          affordability_profile: formData.affordability_profile || 'BALANCED',
        }),
        api.getRecommendations(formData),
      ]);

      if (affordRes.status === 'fulfilled') {
        setAffordabilityData(affordRes.value);
      }
      if (recRes.status === 'fulfilled') {
        setRecommendationData(recRes.value);
      } else if (affordRes.status === 'rejected') {
        throw affordRes.reason;
      }
    } catch (err: any) {
      console.error('Failed to calculate affordability:', err);
      setErrorMsg(err.message || 'Unable to calculate affordability. Ensure the backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
        {/* Hero Banner */}
        <section className="text-center max-w-3xl mx-auto space-y-3 pt-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>State RTO Taxes • Bank Loan Rates • Real-world TCO</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white">
            Find the Cars in India You Can <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300">Truly Afford</span>
          </h1>
          <p className="text-sm sm:text-base text-slate-400">
            CarAfford calculates exact State/RTO on-road pricing, banking eligibility, and monthly Total Cost of Ownership (EMI + Fuel + Insurance + Maintenance) to give you safe, realistic car recommendations.
          </p>
        </section>

        {/* Form and Budget Meter */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Form Column */}
          <div className="lg:col-span-6 space-y-6">
            <AffordabilityForm onCalculate={handleCalculate} isLoading={isLoading} />
          </div>

          {/* Budget & Insights Column */}
          <div className="lg:col-span-6 space-y-6">
            {affordabilityData || recommendationData ? (
              <BudgetSummaryCard summary={affordabilityData || recommendationData!.user_budget_summary} />
            ) : (
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 text-center space-y-3">
                <div className="w-12 h-12 rounded-xl bg-slate-800/80 mx-auto flex items-center justify-center text-slate-400">
                  <Car className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-white">Enter your income & preferences</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  We will compute your maximum bank loan eligibility, safe monthly budget, and rank matching Indian cars by affordability score.
                </p>
              </div>
            )}

            {/* Indian Car Buying Financial Rules Card */}
            <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Smart Indian Car Buying Benchmarks
              </h3>
              <ul className="text-xs text-slate-300 space-y-2">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span><strong>The 20/4/10 Rule:</strong> Aim for at least 20% down payment, a loan tenure under 4-5 years, and keep total car expenses under 10-20% of net pay.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span><strong>FOIR Banking Limit:</strong> Indian banks usually approve auto loans only if your total EMIs (Home + Auto + Personal) stay below 40-50% of take-home pay.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span><strong>Hidden On-Road Costs:</strong> In India, RTO Road Tax + TCS + 3-Yr Insurance adds 12% to 22% over ex-showroom pricing.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Error Alert if any */}
        {errorMsg && (
          <div className="bg-rose-950/40 border border-rose-500/30 rounded-2xl p-4 flex items-center gap-3 text-rose-300 text-sm">
            <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Recommended Cars Section */}
        {recommendationData && (
          <section className="space-y-6 pt-6 border-t border-slate-800">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <Car className="w-6 h-6 text-emerald-400" />
                  Recommended Cars for Your Budget
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Showing {recommendationData.total_matches_count} matching variants ranked by Affordability Score, Safety Rating, and Total Cost of Ownership.
                </p>
              </div>
            </div>

            {recommendationData.recommended_vehicles.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {recommendationData.recommended_vehicles.map((car) => (
                  <CarRecommendationCard key={car.variant_id} car={car} />
                ))}
              </div>
            ) : (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
                <p className="text-base font-semibold text-slate-200">No cars found within this specific price bracket.</p>
                <p className="text-xs text-slate-400">
                  Try adjusting down payment, extending tenure, or relaxing body/fuel type filters.
                </p>
              </div>
            )}
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-8 text-center text-xs text-slate-500 mt-16">
        <div className="max-w-7xl mx-auto px-4 space-y-2">
          <p>© {new Date().getFullYear()} CarAfford. Designed for Indian Car Buyers.</p>
          <p className="text-[11px] text-slate-600">
            On-road prices and loan interest rates are indicative estimates based on official RTO slabs and benchmark retail banking rates.
          </p>
        </div>
      </footer>
    </div>
  );
}
