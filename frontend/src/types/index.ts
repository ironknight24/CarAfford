export interface State {
  id: number;
  name: string;
  code: string;
  is_ut: boolean;
}

export interface City {
  id: number;
  name: string;
  slug: string;
  state_id: number;
  tier: string;
}

export interface Manufacturer {
  id: number;
  name: string;
  slug: string;
  country_of_origin: string;
  logo_url?: string;
  is_active: boolean;
}

export interface VariantSpecification {
  id: number;
  variant_id: number;
  engine_displacement_cc?: number;
  battery_capacity_kwh?: number;
  max_power_bhp?: number;
  max_torque_nm?: number;
  arai_mileage_kmpl: number;
  fuel_tank_capacity_l?: number;
  boot_space_l?: number;
  airbags_count: number;
  safety_rating_stars?: number;
  ground_clearance_mm?: number;
}

export interface Variant {
  id: number;
  model_id: number;
  name: string;
  slug: string;
  trim_level: string;
  fuel_type: string;
  transmission: string;
  seating_capacity: number;
  is_active: boolean;
  model?: {
    id: number;
    name: string;
    slug: string;
    body_type: string;
    image_url?: string;
    manufacturer?: Manufacturer;
  };
  specification?: VariantSpecification;
}

export interface OnRoadPriceBreakdown {
  variant_id: number;
  variant_name: string;
  model_name: string;
  manufacturer_name: string;
  state_id: number;
  state_name: string;
  city_name?: string;
  ex_showroom_price: string;
  rto_road_tax: string;
  rto_road_tax_percent: string;
  rto_cess: string;
  registration_charges: string;
  fastag_charges: string;
  green_cess: string;
  hypothecation_charges: string;
  tcs_amount: string;
  insurance_estimated_idv: string;
  insurance_third_party_3yr: string;
  insurance_own_damage_1yr: string;
  insurance_zero_dep_addon: string;
  insurance_total: string;
  on_road_price: string;
  is_bh_series: boolean;
  calculated_at: string;
}

export interface OwnershipCostBreakdown {
  monthly_emi: string;
  monthly_fuel_cost: string;
  monthly_insurance_cost: string;
  monthly_maintenance_cost: string;
  total_monthly_tco: string;
  tco_percentage_of_income: string;
}

export interface AffordabilityBudgetSummary {
  monthly_take_home_income: string;
  existing_monthly_emis: string;
  max_total_emi_allowed: string;
  available_car_emi_budget: string;
  available_down_payment: string;
  max_affordable_loan: string;
  max_affordable_on_road_price: string;
  recommended_on_road_budget: string;
  estimated_interest_rate: string;
  tenure_months: number;
  cibil_score: number;
  foir_used_percent: string;
}

export type AffordabilityCategory = 'Comfortable' | 'Balanced' | 'Stretch' | 'Risky';

export interface RecommendedVehicleItem {
  variant_id: number;
  variant_name: string;
  model_name: string;
  model_slug: string;
  manufacturer_name: string;
  manufacturer_slug: string;
  body_type: string;
  fuel_type: string;
  transmission: string;
  seating_capacity: number;
  image_url?: string;
  arai_mileage_kmpl: string;
  safety_rating_stars?: number;
  airbags_count: number;
  ex_showroom_price: string;
  on_road_price: string;
  down_payment_required: string;
  loan_amount: string;
  estimated_monthly_emi: string;
  interest_rate: string;
  tenure_months: number;
  ownership_cost: OwnershipCostBreakdown;
  affordability_score: number;
  affordability_category: AffordabilityCategory;
  affordability_rationale: string;
  on_road_breakdown?: OnRoadPriceBreakdown;
}

export interface RecommendationResponse {
  user_budget_summary: AffordabilityBudgetSummary;
  recommended_vehicles: RecommendedVehicleItem[];
  total_matches_count: number;
  filter_applied_count: number;
}

export interface DataSource {
  id: number;
  name: string;
  slug: string;
  provider_type: string;
  base_url?: string;
  description?: string;
  is_active: boolean;
  last_synced_at?: string;
}
