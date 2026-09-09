'use client';

import React, { useEffect, useState } from 'react';
import { Car, Search, Filter, Fuel, Shield, ChevronRight, FileText } from 'lucide-react';
import Navbar from '@/components/Navbar';
import CostBreakdownModal from '@/components/CostBreakdownModal';
import { OnRoadPriceBreakdown, State, Variant } from '@/types';
import { api } from '@/lib/api';
import { formatINR, formatINRLakhs } from '@/lib/utils';

export default function ExplorePage() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [states, setStates] = useState<State[]>([]);
  const [selectedState, setSelectedState] = useState<number>(1);
  const [isBhSeries, setIsBhSeries] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');
  const [fuelFilter, setFuelFilter] = useState<string>('ALL');
  const [bodyFilter, setBodyFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState<boolean>(true);

  // Modal breakdown state
  const [activeModalBreakdown, setActiveModalBreakdown] = useState<OnRoadPriceBreakdown | null>(null);
  const [activeCarName, setActiveCarName] = useState<string>('');
  const [modalLoading, setModalLoading] = useState<boolean>(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [stList, vList] = await Promise.all([
          api.getStates(),
          api.getVariants(),
        ]);
        if (stList && stList.length > 0) {
          setStates(stList);
          setSelectedState(stList[0].id);
        }
        setVariants(vList || []);
      } catch (err) {
        console.error('Failed to load explore catalog:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleOpenBreakdown = async (variant: Variant) => {
    setModalLoading(true);
    setActiveCarName(`${variant.model?.manufacturer?.name || ''} ${variant.model?.name || ''} - ${variant.name}`);
    try {
      const breakdown = await api.getOnRoadPrice({
        variant_id: variant.id,
        state_id: selectedState,
        is_bh_series: isBhSeries,
        include_zero_dep_insurance: true,
        is_financed: true,
      });
      setActiveModalBreakdown(breakdown);
    } catch (e) {
      console.error('Failed to compute on-road breakdown:', e);
    } finally {
      setModalLoading(false);
    }
  };

  const filteredVariants = variants.filter((v) => {
    const matchesSearch =
      !search ||
      v.name.toLowerCase().includes(search.toLowerCase()) ||
      v.model?.name.toLowerCase().includes(search.toLowerCase()) ||
      v.model?.manufacturer?.name.toLowerCase().includes(search.toLowerCase());

    const matchesFuel = fuelFilter === 'ALL' || v.fuel_type === fuelFilter;
    const matchesBody = bodyFilter === 'ALL' || v.model?.body_type === bodyFilter;

    return matchesSearch && matchesFuel && matchesBody;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
            <Car className="w-8 h-8 text-emerald-400" />
            Explore Indian Cars & State On-Road Prices
          </h1>
          <p className="text-sm text-slate-400">
            Browse ex-showroom prices, state RTO taxes, insurance estimates, and safety ratings across popular car models in India.
          </p>
        </div>

        {/* Location & Surcharges Bar */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-300">Select Registration State:</span>
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(Number(e.target.value))}
              className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500 cursor-pointer"
            >
              {states.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={isBhSeries}
                onChange={(e) => setIsBhSeries(e.target.checked)}
                className="rounded accent-emerald-400 w-4 h-4 cursor-pointer"
              />
              <span>Calculate with <strong>BH (Bharat) Series</strong> Tax</span>
            </label>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search car model or brand (e.g. Nexon, Creta, Swift)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <select
              value={fuelFilter}
              onChange={(e) => setFuelFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500 cursor-pointer"
            >
              <option value="ALL">All Fuel Types</option>
              <option value="Petrol">Petrol</option>
              <option value="Diesel">Diesel</option>
              <option value="CNG">CNG</option>
              <option value="Electric">Electric (EV)</option>
            </select>
          </div>

          <div>
            <select
              value={bodyFilter}
              onChange={(e) => setBodyFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500 cursor-pointer"
            >
              <option value="ALL">All Body Types</option>
              <option value="SUV">SUV</option>
              <option value="Hatchback">Hatchback</option>
              <option value="Sedan">Sedan</option>
            </select>
          </div>
        </div>

        {/* Catalog Grid */}
        {loading ? (
          <div className="p-12 text-center text-sm text-slate-400">Loading vehicle catalog...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredVariants.map((v) => (
              <div
                key={v.id}
                className="bg-slate-900/90 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 space-y-4 flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-[11px] font-semibold text-slate-400 uppercase">
                        {v.model?.manufacturer?.name}
                      </span>
                      <h3 className="text-base font-bold text-white">{v.model?.name}</h3>
                      <p className="text-xs text-slate-400 line-clamp-1">{v.name}</p>
                    </div>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      {v.fuel_type}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 mt-3 text-[11px] text-slate-400">
                    <span className="px-2 py-0.5 bg-slate-950 rounded border border-slate-800">{v.transmission}</span>
                    <span className="px-2 py-0.5 bg-slate-950 rounded border border-slate-800">{v.model?.body_type}</span>
                    <span className="px-2 py-0.5 bg-slate-950 rounded border border-slate-800">{v.seating_capacity} Seater</span>
                    {v.specification?.arai_mileage_kmpl && (
                      <span className="px-2 py-0.5 bg-slate-950 rounded border border-slate-800 text-emerald-400">
                        {v.specification.arai_mileage_kmpl} km/l
                      </span>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => handleOpenBreakdown(v)}
                  className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-emerald-500 hover:text-slate-950 text-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all duration-200"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Calculate On-Road Price in {states.find((s) => s.id === selectedState)?.name || 'State'}</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </main>

      <CostBreakdownModal
        isOpen={activeModalBreakdown !== null}
        onClose={() => setActiveModalBreakdown(null)}
        carName={activeCarName}
        onRoadBreakdown={activeModalBreakdown || undefined}
      />
    </div>
  );
}
