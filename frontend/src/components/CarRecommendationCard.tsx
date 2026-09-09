'use client';

import React, { useState } from 'react';
import { Shield, Fuel, Gauge, Check, Info, Star, ChevronRight } from 'lucide-react';
import { RecommendedVehicleItem } from '@/types';
import { formatINR, formatINRLakhs } from '@/lib/utils';
import CostBreakdownModal from './CostBreakdownModal';

interface CarRecommendationCardProps {
  car: RecommendedVehicleItem;
}

export default function CarRecommendationCard({ car }: CarRecommendationCardProps) {
  const [showModal, setShowModal] = useState(false);

  const getCategoryBadge = () => {
    switch (car.affordability_category) {
      case 'Comfortable':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'Balanced':
        return 'bg-teal-500/10 text-teal-400 border-teal-500/30';
      case 'Stretch':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'Risky':
      default:
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    }
  };

  return (
    <>
      <div className="group bg-slate-900/90 hover:bg-slate-900 border border-slate-800 hover:border-emerald-500/40 rounded-2xl p-5 transition-all duration-200 shadow-lg hover:shadow-emerald-500/5 flex flex-col justify-between relative overflow-hidden">
        {/* Top Header */}
        <div>
          <div className="flex items-start justify-between gap-2 mb-3">
            <div>
              <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                {car.manufacturer_name}
              </span>
              <h3 className="text-lg font-bold text-white group-hover:text-emerald-300 transition-colors">
                {car.model_name}
              </h3>
              <p className="text-xs text-slate-400 font-medium line-clamp-1">{car.variant_name}</p>
            </div>

            {/* Category and Affordability Badges */}
            <div className="flex flex-col items-end gap-1">
              {car.category && (
                <span className="text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 uppercase">
                  {car.category.replace(/_/g, ' ')}
                </span>
              )}
              <div className="flex items-center gap-1.5">
                <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${getCategoryBadge()}`}>
                  {car.affordability_category}
                </span>
                <span className="text-[11px] text-slate-400 font-medium">
                  Score: <strong className="text-emerald-400">{car.score || car.affordability_score}</strong>/100
                </span>
              </div>
            </div>
          </div>

          {/* Quick Spec Pills */}
          <div className="flex flex-wrap gap-1.5 mb-4 text-[11px] font-medium text-slate-300">
            <span className="px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/50">
              {car.fuel_type}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/50">
              {car.transmission}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/50">
              {car.body_type}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/50 flex items-center gap-1">
              <Fuel className="w-3 h-3 text-emerald-400" />
              {car.arai_mileage_kmpl} km/l
            </span>
            {car.safety_rating_stars && (
              <span className="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-300 flex items-center gap-0.5">
                <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                {car.safety_rating_stars}-Star Safety
              </span>
            )}
          </div>

          {/* Pricing Row */}
          <div className="bg-slate-950/70 rounded-xl p-3.5 border border-slate-800/80 space-y-2 mb-3">
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-slate-400">Est. On-Road Price</span>
              <span className="text-base font-extrabold text-white">
                {formatINRLakhs(car.on_road_price)}
              </span>
            </div>
            <div className="flex justify-between items-baseline border-t border-slate-800/80 pt-2 text-xs">
              <span className="text-slate-400">Monthly Loan EMI</span>
              <span className="font-bold text-emerald-400">
                {formatINR(car.estimated_monthly_emi)} <span className="text-[10px] text-slate-400 font-normal">/ mo</span>
              </span>
            </div>
            <div className="flex justify-between items-baseline text-xs text-slate-400">
              <span>Total Monthly TCO</span>
              <span className="font-semibold text-slate-200">
                {formatINR(car.ownership_cost.total_monthly_tco)} <span className="text-[10px] text-slate-400 font-normal">/ mo</span>
              </span>
            </div>
          </div>

          {/* Why this car? Reasons */}
          {car.reasons && car.reasons.length > 0 ? (
            <div className="mb-3 space-y-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Why this car?</span>
              <ul className="space-y-1">
                {car.reasons.slice(0, 3).map((reason, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-1.5 leading-relaxed">
                    <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic mb-4 line-clamp-2">
              "{car.affordability_rationale}"
            </p>
          )}
        </div>

        {/* Action Button */}
        <button
          onClick={() => setShowModal(true)}
          className="w-full mt-2 py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-emerald-600 hover:text-slate-950 text-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all duration-200 group-hover:border group-hover:border-emerald-500/30"
        >
          <span>View Detailed Cost Breakdown</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <CostBreakdownModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        carName={`${car.manufacturer_name} ${car.model_name} - ${car.variant_name}`}
        onRoadBreakdown={car.on_road_breakdown}
        ownershipCost={car.ownership_cost}
      />
    </>
  );
}
