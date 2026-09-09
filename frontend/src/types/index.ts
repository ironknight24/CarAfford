export interface Country {
  id: number;
  name: string;
  iso_code: string;
  iso3_code: string;
  active: boolean;
  states_count?: number;
  states?: State[];
}

export interface State {
  id: number;
  country_id: number;
  name: string;
  code: string;
  region_type: string;
  active: boolean;
  is_ut: boolean;
  country?: Country;
  cities_count?: number;
  rtos_count?: number;
  cities?: City[];
  rtos?: RtoOffice[];
}

export interface City {
  id: number;
  state_id: number;
  name: string;
  slug: string;
  tier: string;
  active: boolean;
  state?: State;
  rtos?: RtoOffice[];
}

export interface RtoOffice {
  id: number;
  state_id: number;
  city_id?: number;
  code: string;
  name: string;
  jurisdiction?: string;
  active: boolean;
  source_id?: number;
  source_record_id?: string;
  retrieved_at?: string;
  created_at?: string;
  updated_at?: string;
  state?: State;
  city?: City;
}

export type RTO = RtoOffice;

export interface LocationSearchItem {
  country_id: number;
  country_name: string;
  country_iso: string;
  state_id: number;
  state_name: string;
  state_code: string;
  region_type: string;
  city_id?: number;
  city_name?: string;
  city_slug?: string;
  rto_id?: number;
  rto_code?: string;
  rto_name?: string;
  rto_jurisdiction?: string;
  match_type: 'rto' | 'city' | 'state' | 'country' | string;
  active: boolean;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Manufacturer {
  id: number;
  name: string;
  slug: string;
  country: string;
  country_of_origin?: string;
  active: boolean;
  is_active?: boolean;
  logo_url?: string;
  models_count?: number;
  models?: CarModel[];
}

export interface CarModel {
  id: number;
  manufacturer_id: number;
  name: string;
  slug: string;
  body_type: string;
  segment?: string;
  active: boolean;
  is_active?: boolean;
  launch_date?: string;
  discontinued_date?: string;
  launch_year?: number;
  description?: string;
  image_url?: string;
  manufacturer?: Manufacturer;
  variants_count?: number;
  variants?: Variant[];
}

export interface VehiclePrice {
  id: number;
  variant_id: number;
  ex_showroom_price: string;
  price_type: 'EX_SHOWROOM' | 'INTRODUCTORY' | 'PROMOTIONAL' | 'OTHER' | string;
  effective_from: string;
  effective_to?: string;
  source_id?: number;
  source_record_id?: string;
  retrieved_at?: string;
  created_at: string;
}

export interface VehicleMedia {
  id: number;
  variant_id?: number;
  model_id?: number;
  media_type: string;
  url: string;
  alt_text?: string;
  sort_order: number;
  active: boolean;
  created_at: string;
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
  drivetrain?: string;
  engine_cc?: number;
  engine_power_bhp?: string;
  torque_nm?: string;
  seating_capacity: number;
  mileage_claimed?: string;
  battery_capacity_kwh?: string;
  range_km?: string;
  active: boolean;
  is_active?: boolean;
  model?: CarModel;
  specification?: VariantSpecification;
  current_price?: VehiclePrice;
  price_history?: VehiclePrice[];
  media?: VehicleMedia[];
}

export interface VehicleSearchResultItem {
  variant_id: number;
  variant_name: string;
  variant_slug: string;
  trim_level: string;
  model_id: number;
  model_name: string;
  model_slug: string;
  body_type: string;
  segment?: string;
  manufacturer_id: number;
  manufacturer_name: string;
  manufacturer_slug: string;
  country: string;
  fuel_type: string;
  transmission: string;
  drivetrain?: string;
  seating_capacity: number;
  engine_cc?: number;
  engine_power_bhp?: string;
  torque_nm?: string;
  mileage_claimed?: string;
  battery_capacity_kwh?: string;
  range_km?: string;
  active: boolean;
  current_ex_showroom_price?: string;
  price_type?: string;
  price_effective_from?: string;
  image_url?: string;
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

export interface TaxRuleBracket {
  id?: number;
  tax_rule_id?: number;
  bracket_order: number;
  minimum_value: string | number;
  maximum_value?: string | number | null;
  rate?: string | number | null;
  fixed_amount?: string | number | null;
  calculation_method: string;
}

export interface TaxRule {
  id: number;
  name: string;
  description?: string;
  state_id: number;
  city_id?: number;
  rto_id?: number;
  rule_category: string;
  tax_type: string;
  calculation_method: string;
  vehicle_type: string;
  fuel_type?: string;
  is_ev?: boolean;
  usage_type: string;
  min_price?: string;
  max_price?: string;
  min_engine_cc?: number;
  max_engine_cc?: number;
  rate?: string;
  fixed_amount?: string;
  base_amount_type: string;
  formula_definition?: Record<string, any>;
  priority: number;
  effective_from: string;
  effective_to?: string;
  active: boolean;
  source_id?: number;
  source_record_id?: string;
  retrieved_at?: string;
  created_at: string;
  updated_at: string;
  brackets?: TaxRuleBracket[];
  state?: State;
  city?: City;
  rto?: RtoOffice;
  source?: DataSource;
}

export interface ResolvedTaxRuleItem {
  rule_id: number;
  name: string;
  description?: string;
  rule_category: string;
  tax_type: string;
  calculation_method: string;
  rate?: string;
  fixed_amount?: string;
  base_amount_type: string;
  brackets: TaxRuleBracket[];
  formula_definition?: Record<string, any>;
  priority: number;
  precedence_tier: number;
  precedence_label: string;
  effective_from: string;
  effective_to?: string;
  source_name?: string;
  source_url?: string;
  source_record_id?: string;
  retrieved_at?: string;
}

export interface TaxRuleResolveResponse {
  location: {
    state_id: number;
    state_name: string;
    state_code: string;
    city_id?: number;
    city_name?: string;
    rto_id?: number;
    rto_code?: string;
    rto_name?: string;
  };
  vehicle: {
    variant_id?: number;
    variant_name?: string;
    model_name?: string;
    manufacturer_name?: string;
    fuel_type: string;
    engine_cc?: number;
    ex_showroom_price: string;
    is_ev: boolean;
    vehicle_type: string;
    usage_type: string;
  };
  calculation_date: string;
  is_bh_series: boolean;
  is_financed: boolean;
  rules: ResolvedTaxRuleItem[];
  rules_count: number;
}

