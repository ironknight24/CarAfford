import {
  CarModel,
  City,
  Country,
  DataSource,
  LocationSearchItem,
  Manufacturer,
  OnRoadPriceBreakdown,
  PaginatedResult,
  RecommendationResponse,
  RtoOffice,
  State,
  Variant,
  VehicleSearchResultItem,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      throw new Error(errorBody.message || errorBody.detail || `HTTP Error ${res.status}`);
    }

    const json = await res.json();
    return json.data !== undefined ? json.data : json;
  } catch (err: any) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // ==========================================
  // Location Hierarchy & Search
  // ==========================================
  getCountries: (params?: { page?: number; page_size?: number; active?: boolean; search?: string }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<Country>>(`/countries${query ? `?${query}` : ''}`);
  },
  getCountryById: (id: number) => fetchJson<Country>(`/countries/${id}`),

  getStates: async () => {
    try {
      const res: any = await fetchJson('/locations/states');
      if (Array.isArray(res)) return res;
      if (res && Array.isArray(res.data)) return res.data;
      if (res && Array.isArray(res.items)) return res.items;
    } catch {
      // Fallback to /states
    }
    const res: any = await fetchJson('/states?page_size=100');
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.items)) return res.items;
    if (res && Array.isArray(res.data)) return res.data;
    return [];
  },
  getStatesPaginated: (params?: {
    page?: number;
    page_size?: number;
    country_id?: number;
    region_type?: string;
    active?: boolean;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<State>>(`/states${query ? `?${query}` : ''}`);
  },
  getStateById: (id: number) => fetchJson<State>(`/states/${id}`),

  getCities: (params?: {
    page?: number;
    page_size?: number;
    state_id?: number;
    tier?: string;
    active?: boolean;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<City>>(`/cities${query ? `?${query}` : ''}`);
  },
  getCitiesByState: async (stateId: number) => {
    if (!stateId) return [];
    const res: any = await fetchJson(`/states/${stateId}/cities`);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.data)) return res.data;
    if (res && Array.isArray(res.items)) return res.items;
    return [];
  },
  getCityById: (id: number) => fetchJson<City>(`/cities/${id}`),

  getRtos: (params?: {
    page?: number;
    page_size?: number;
    state_id?: number;
    city_id?: number;
    active?: boolean;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<RtoOffice>>(`/rtos${query ? `?${query}` : ''}`);
  },
  getRtosByState: async (stateId: number) => {
    if (!stateId) return [];
    const res: any = await fetchJson(`/states/${stateId}/rtos`);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.data)) return res.data;
    if (res && Array.isArray(res.items)) return res.items;
    return [];
  },
  getRtosByCity: async (cityId: number) => {
    if (!cityId) return [];
    const res: any = await fetchJson(`/cities/${cityId}/rtos`);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.data)) return res.data;
    if (res && Array.isArray(res.items)) return res.items;
    return [];
  },
  getRtoById: (id: number) => fetchJson<RtoOffice>(`/rtos/${id}`),

  searchLocations: (query: string, countryId?: number, stateId?: number, cityId?: number) => {
    const searchParams = new URLSearchParams({ q: query });
    if (countryId) searchParams.append('country_id', String(countryId));
    if (stateId) searchParams.append('state_id', String(stateId));
    if (cityId) searchParams.append('city_id', String(cityId));
    return fetchJson<LocationSearchItem[]>(`/locations/search?${searchParams.toString()}`);
  },

  // ==========================================
  // Vehicle Catalogue
  // ==========================================
  getManufacturers: (params?: { page?: number; page_size?: number; active?: boolean; search?: string }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<Manufacturer>>(`/manufacturers${query ? `?${query}` : ''}`);
  },
  getManufacturerById: (id: number) => fetchJson<Manufacturer>(`/manufacturers/${id}`),

  getModels: (params?: {
    page?: number;
    page_size?: number;
    manufacturer_id?: number;
    body_type?: string;
    segment?: string;
    active?: boolean;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<CarModel>>(`/models${query ? `?${query}` : ''}`);
  },
  getModelById: (id: number) => fetchJson<CarModel>(`/models/${id}`),

  getVariants: (params?: Record<string, any>) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<Variant>>(`/variants${query ? `?${query}` : ''}`);
  },
  getVariantById: (variantId: number) => fetchJson<Variant>(`/variants/${variantId}`),

  searchVehicles: (params?: {
    manufacturer?: string;
    manufacturer_id?: number;
    model?: string;
    model_id?: number;
    fuel_type?: string;
    transmission?: string;
    body_type?: string;
    segment?: string;
    minimum_price?: number | string;
    maximum_price?: number | string;
    minimum_seating_capacity?: number;
    active?: boolean;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<VehicleSearchResultItem>>(`/vehicles/search${query ? `?${query}` : ''}`);
  },

  // ==========================================
  // On-road Pricing & Affordability
  // ==========================================
  calculateOnRoadPrice: (req: import('@/types').OnRoadPriceCalculationRequest) =>
    fetchJson<import('@/types').OnRoadPriceResponse>('/pricing/on-road', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  getOnRoadPriceByVariant: (
    variant_id: number,
    params: {
      state_id: number;
      city_id?: number;
      rto_id?: number;
      calculation_date?: string;
      insurance_option?: string;
      insurance_amount?: number | string;
      is_bh_series?: boolean;
      is_financed?: boolean;
    }
  ) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, String(val));
      }
    });
    const query = searchParams.toString();
    return fetchJson<import('@/types').OnRoadPriceResponse>(
      `/pricing/on-road/${variant_id}?${query}`
    );
  },

  getOnRoadPrice: (req: {
    variant_id: number;
    state_id: number;
    city_id?: number;
    is_bh_series?: boolean;
    include_zero_dep_insurance?: boolean;
    is_financed?: boolean;
  }) =>
    fetchJson<OnRoadPriceBreakdown>('/pricing/on-road-breakdown', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  getRecommendations: (payload: {
    monthly_take_home_income: number | string;
    existing_monthly_emis?: number | string;
    available_down_payment?: number | string;
    state_id: number;
    city_id?: number;
    desired_tenure_months?: number;
    cibil_score?: number;
    monthly_commute_km?: number;
    preferred_body_types?: string[];
    preferred_fuel_types?: string[];
    preferred_transmission?: string[];
    min_seating?: number;
    min_safety_rating?: number;
  }) =>
    fetchJson<RecommendationResponse>('/recommendations', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  calculateLegacyEmi: (payload: {
    principal_amount: number | string;
    annual_interest_rate: number | string;
    tenure_months: number;
  }) =>
    fetchJson<any>('/finance/calculate-emi?generate_schedule=false', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getDataSources: () => fetchJson<DataSource[]>('/data-sources'),

  // ==========================================
  // Tax & Registration Rules Domain
  // ==========================================
  getTaxRules: (params?: {
    skip?: number;
    limit?: number;
    state_id?: number;
    city_id?: number;
    rto_id?: number;
    tax_type?: string;
    rule_category?: string;
    calculation_method?: string;
    fuel_type?: string;
    active?: boolean;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<PaginatedResult<import('@/types').TaxRule>>(`/tax-rules${query ? `?${query}` : ''}`);
  },

  getTaxRuleById: (id: number) =>
    fetchJson<import('@/types').TaxRule>(`/tax-rules/${id}`),

  resolveTaxRules: (params: {
    state_id: number;
    city_id?: number;
    rto_id?: number;
    variant_id?: number;
    fuel_type?: string;
    engine_cc?: number;
    ex_showroom_price?: number | string;
    is_ev?: boolean;
    vehicle_type?: string;
    usage_type?: string;
    calculation_date?: string;
    is_bh_series?: boolean;
    is_financed?: boolean;
  }) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, String(val));
      }
    });
    const query = searchParams.toString();
    return fetchJson<import('@/types').TaxRuleResolveResponse>(`/tax-rules/resolve?${query}`);
  },

  // ==========================================
  // Bank & Car Loan Financing APIs
  // ==========================================
  getBanks: (params?: { page?: number; page_size?: number; active?: boolean; search?: string }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && String(val) !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<import('@/types').PaginatedResult<import('@/types').Bank>>(`/finance/banks${query ? `?${query}` : ''}`);
  },

  getBankById: (id: number) =>
    fetchJson<import('@/types').Bank>(`/finance/banks/${id}`),

  getLoanProducts: (params?: {
    page?: number;
    page_size?: number;
    bank_id?: number;
    vehicle_type?: string;
    vehicle_condition?: string;
    product_category?: string;
    active?: boolean;
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && String(val) !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<import('@/types').PaginatedResult<import('@/types').LoanProduct>>(`/finance/loan-products${query ? `?${query}` : ''}`);
  },

  getLoanProductById: (id: number) =>
    fetchJson<import('@/types').LoanProduct>(`/finance/loan-products/${id}`),

  getInterestRates: (params?: {
    page?: number;
    page_size?: number;
    loan_product_id?: number;
    active?: boolean;
  }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && String(val) !== '') {
          searchParams.append(key, String(val));
        }
      });
    }
    const query = searchParams.toString();
    return fetchJson<import('@/types').PaginatedResult<import('@/types').InterestRate>>(`/finance/rates${query ? `?${query}` : ''}`);
  },

  calculateFinance: (request: import('@/types').FinanceCalculationRequest) =>
    fetchJson<import('@/types').FinanceCalculationResponse>('/finance/calculate', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  compareBankFinancing: (request: import('@/types').BankComparisonRequest) =>
    fetchJson<import('@/types').BankComparisonResponse>('/finance/compare', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  calculateEmi: (request: import('@/types').EmiCalculationRequest) =>
    fetchJson<import('@/types').EmiCalculationResponse>('/finance/emi', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  calculateMaxLoan: (request: import('@/types').MaxLoanCalculationRequest) =>
    fetchJson<import('@/types').MaxLoanCalculationResponse>('/finance/max-loan', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  getAmortizationSchedule: (request: import('@/types').AmortizationScheduleRequest) =>
    fetchJson<import('@/types').AmortizationScheduleResponse>('/finance/amortization', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // ==========================================
  // Affordability Engine APIs
  // ==========================================
  getAffordabilityProfiles: () =>
    fetchJson<import('@/types').AffordabilityProfileInfo[]>('/affordability/profiles'),

  calculateAffordability: (request: import('@/types').AffordabilityCalculateRequest) =>
    fetchJson<import('@/types').AffordabilityBudgetBreakdown>('/affordability/calculate', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  evaluateVehicleAffordability: (request: import('@/types').VehicleAffordabilityRequest) =>
    fetchJson<import('@/types').VehicleAffordabilityResponse>('/affordability/vehicle', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  evaluateMultipleVehiclesAffordability: (request: import('@/types').MultiVehicleAffordabilityRequest) =>
    fetchJson<import('@/types').MultiVehicleAffordabilityResponse>('/affordability/vehicles', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  compareVehiclesAffordability: (request: import('@/types').AffordabilityComparisonRequest) =>
    fetchJson<import('@/types').AffordabilityComparisonResponse>('/affordability/compare', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // ==========================================
  // Total Cost of Ownership (TCO) APIs
  // ==========================================
  getTCOAssumptions: () =>
    fetchJson<import('@/types').TCOAssumptionsResponse>('/tco/assumptions'),

  calculateTCO: (request: import('@/types').TCOCalculationRequest) =>
    fetchJson<import('@/types').TCOCalculationResponse>('/tco/calculate', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  calculateVehicleTCO: (request: import('@/types').TCOVehicleRequest) =>
    fetchJson<import('@/types').TCOCalculationResponse>('/tco/vehicle', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  compareVehiclesTCO: (request: import('@/types').TCOComparisonRequest) =>
    fetchJson<import('@/types').TCOComparisonResponse>('/tco/compare', {
      method: 'POST',
      body: JSON.stringify(request),
    }),
};


