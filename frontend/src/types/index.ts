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

export interface OnRoadPriceCalculationRequest {
  variant_id: number;
  state_id: number;
  city_id?: number;
  rto_id?: number;
  calculation_date?: string;
  insurance_option?: 'DEFAULT_ESTIMATE' | 'USER_PROVIDED' | 'ZERO_DEP' | 'THIRD_PARTY_ONLY' | string;
  insurance_amount?: number | string;
  is_bh_series?: boolean;
  is_financed?: boolean;
}

export interface PriceBreakdownItem {
  component: string;
  tax_rule_id?: number;
  rule_name: string;
  calculation_method: string;
  base_amount?: string | number;
  rate?: string | number;
  fixed_amount?: string | number;
  calculated_amount: string | number;
  source?: string;
  source_url?: string;
  effective_from?: string;
  effective_to?: string;
  explanation?: string;
  is_estimated: boolean;
  status: string;
}

export interface OnRoadPriceTotals {
  ex_showroom_price: string | number;
  total_statutory_taxes: string | number;
  total_registration_and_fees: string | number;
  total_insurance: string | number;
  total_other_charges: string | number;
  on_road_price: string | number;
}

export interface DataQualityInfo {
  is_estimated: boolean;
  has_demo_rules: boolean;
  data_status: 'AUTHORITATIVE' | 'DEMO' | 'PROVISIONAL' | string;
  sources: string[];
  disclaimer: string;
}

export interface OnRoadPriceResponse {
  vehicle: {
    variant_id: number;
    variant_name: string;
    model_name?: string;
    manufacturer_name?: string;
    fuel_type: string;
    engine_cc?: number;
    ex_showroom_price: string | number;
    is_ev: boolean;
    vehicle_type: string;
    usage_type: string;
  };
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
  calculation_date: string;
  is_bh_series: boolean;
  is_financed: boolean;
  insurance_option: string;
  breakdown: PriceBreakdownItem[];
  totals: OnRoadPriceTotals;
  data_quality: DataQualityInfo;
}

// =============================================================================
// BANK & CAR LOAN FINANCING DOMAIN TYPES
// =============================================================================

export interface Bank {
  id: number;
  name: string;
  slug: string;
  bank_type: string;
  website_url?: string;
  logo_url?: string;
  active: boolean;
  is_active?: boolean;
  source_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface InterestRate {
  id: number;
  loan_product_id: number;
  annual_interest_rate: string | number;
  rate_type: 'FIXED' | 'FLOATING' | 'VARIABLE' | string;
  min_credit_score?: number;
  max_credit_score?: number;
  min_tenure_months?: number;
  max_tenure_months?: number;
  min_loan_amount?: string | number;
  max_loan_amount?: string | number;
  employment_type?: string;
  priority: number;
  effective_from: string;
  effective_to?: string;
  active: boolean;
  source_id?: number;
  source_record_id?: string;
  retrieved_at?: string;
}

export interface LoanEligibilityRule {
  id: number;
  loan_product_id: number;
  rule_name: string;
  min_monthly_income?: string | number;
  min_credit_score?: number;
  max_credit_score?: number;
  max_loan_amount?: string | number;
  max_ltv_percent?: string | number;
  max_foir_percent?: string | number;
  min_age_years?: number;
  max_age_years?: number;
  min_employment_months?: number;
  allowed_employment_types?: string;
  allowed_residency_types?: string;
  effective_from: string;
  effective_to?: string;
  active: boolean;
}

export interface LoanFee {
  id: number;
  loan_product_id: number;
  fee_name: string;
  fee_type: string;
  calculation_method: string;
  fixed_amount?: string | number;
  percentage?: string | number;
  minimum_amount?: string | number;
  maximum_amount?: string | number;
  effective_from: string;
  effective_to?: string;
  active: boolean;
}

export interface LoanProduct {
  id: number;
  bank_id: number;
  name: string;
  slug: string;
  vehicle_type: string;
  vehicle_condition: string;
  product_category: string;
  min_loan_amount: string | number;
  max_loan_amount: string | number;
  min_tenure_months: number;
  max_tenure_months: number;
  max_ltv_percent: string | number;
  processing_fee_percent: string | number;
  min_processing_fee: string | number;
  max_processing_fee: string | number;
  description?: string;
  active: boolean;
  bank?: Bank;
  interest_rates?: InterestRate[];
  eligibility_rules?: LoanEligibilityRule[];
  fees?: LoanFee[];
}

export interface FeeBreakdownItem {
  fee_name: string;
  fee_type: string;
  calculation_method: string;
  rate_or_amount?: string | number;
  calculated_amount: string | number;
}

export interface LoanOfferItem {
  bank_id: number;
  bank_name: string;
  bank_slug: string;
  bank_type: string;
  logo_url?: string;
  loan_product_id: number;
  product_name: string;
  product_slug: string;
  product_category: string;
  annual_interest_rate: string | number;
  rate_type: string;
  tenure_months: number;
  principal_loan_amount: string | number;
  monthly_emi: string | number;
  total_interest: string | number;
  total_repayment: string | number;
  ltv_percent: string | number;
  processing_fee: string | number;
  total_fees: string | number;
  fees_breakdown: FeeBreakdownItem[];
  estimated_eligibility: boolean;
  eligibility_status: 'ESTIMATED_ELIGIBLE' | 'MARGINAL' | 'ESTIMATED_INELIGIBLE' | string;
  eligibility_reasons: string[];
  rate_effective_from: string;
  rate_effective_to?: string;
  rate_source_name?: string;
  is_recommended: boolean;
  data_status: string;
  disclaimer: string;
}

export interface AmortizationScheduleItem {
  installment_number: number;
  month: number;
  opening_balance: string | number;
  beginning_balance?: string | number;
  emi: string | number;
  principal_component: string | number;
  principal_paid?: string | number;
  interest_component: string | number;
  interest_paid?: string | number;
  closing_balance: string | number;
  ending_balance?: string | number;
}

export interface FinanceCalculationRequest {
  vehicle_variant_id?: number;
  state_id?: number;
  city_id?: number;
  rto_id?: number;
  on_road_price?: string | number;
  loan_amount?: string | number;
  down_payment?: string | number;
  loan_tenure_months?: number;
  tenure_months?: number;
  credit_score?: number;
  monthly_income?: string | number;
  employment_type?: string;
  applicant_age?: number;
  bank_id?: number;
  loan_product_id?: number;
  calculation_date?: string;
  include_amortization?: boolean;
}

export interface FinanceCalculationResponse {
  variant_id?: number;
  variant_name?: string;
  model_name?: string;
  manufacturer_name?: string;
  on_road_price: string | number;
  down_payment: string | number;
  loan_amount: string | number;
  tenure_months: number;
  credit_score_used: number;
  calculation_date: string;
  selected_offer: LoanOfferItem;
  amortization_schedule?: AmortizationScheduleItem[];
  bank_name?: string;
  applied_interest_rate?: string | number;
  eligibility?: {
    is_eligible: boolean;
    status: string;
    reasons: string[];
  };
  data_quality: {
    is_estimated: boolean;
    data_status: string;
    disclaimer: string;
  };
}

export interface BankComparisonRequest {
  vehicle_variant_id?: number;
  state_id?: number;
  city_id?: number;
  rto_id?: number;
  on_road_price?: string | number;
  loan_amount?: string | number;
  down_payment?: string | number;
  loan_tenure_months?: number;
  tenure_months?: number;
  credit_score?: number;
  monthly_income?: string | number;
  employment_type?: string;
  applicant_age?: number;
  calculation_date?: string;
}

export interface BankComparisonResponse {
  variant_id?: number;
  variant_name?: string;
  model_name?: string;
  manufacturer_name?: string;
  on_road_price: string | number;
  down_payment: string | number;
  loan_amount: string | number;
  tenure_months: number;
  credit_score_used: number;
  calculation_date: string;
  offers: LoanOfferItem[];
  total_offers_count: number;
  eligible_offers_count: number;
  data_quality: {
    is_estimated: boolean;
    data_status: string;
    disclaimer: string;
  };
}

export interface EmiCalculationRequest {
  principal_amount?: string | number;
  loan_amount?: string | number;
  annual_interest_rate: string | number;
  tenure_months: number;
}

export interface EmiCalculationResponse {
  principal_amount: string | number;
  annual_interest_rate: string | number;
  tenure_months: number;
  monthly_emi: string | number;
  total_interest_payable: string | number;
  total_amount_payable: string | number;
  total_payment?: string | number;
  amortization_schedule?: AmortizationScheduleItem[];
}

export interface MaxLoanCalculationRequest {
  maximum_emi?: string | number;
  desired_monthly_emi?: string | number;
  annual_interest_rate: string | number;
  tenure_months: number;
}

export interface MaxLoanCalculationResponse {
  maximum_emi: string | number;
  annual_interest_rate: string | number;
  tenure_months: number;
  maximum_principal: string | number;
  maximum_loan_amount?: string | number;
}

export interface AmortizationScheduleRequest {
  principal?: string | number;
  loan_amount?: string | number;
  annual_interest_rate: string | number;
  tenure_months: number;
}

export interface AmortizationScheduleResponse {
  principal: string | number;
  annual_interest_rate: string | number;
  tenure_months: number;
  monthly_emi: string | number;
  total_interest: string | number;
  total_repayment: string | number;
  schedule: AmortizationScheduleItem[];
}

// ==========================================
// Affordability Engine Domain Types
// ==========================================

export type AffordabilityProfile = 'CONSERVATIVE' | 'BALANCED' | 'STRETCH';

export type AffordabilityStatus =
  | 'COMFORTABLE'
  | 'AFFORDABLE'
  | 'STRETCH'
  | 'NOT_AFFORDABLE'
  | 'NO_FINANCING_OPTION';

export type LimitingFactor =
  | 'EMI_CAP'
  | 'LTV_CAP'
  | 'LOAN_MAXIMUM'
  | 'ELIGIBILITY'
  | 'DOWN_PAYMENT'
  | 'NO_ELIGIBLE_LOAN';

export interface AffordabilityProfileInfo {
  code: AffordabilityProfile;
  name: string;
  max_foir_ratio: string | number;
  max_foir_percent: string | number;
  safe_budget_multiplier: string | number;
  stretch_budget_multiplier: string | number;
  description: string;
}

export interface AffordabilityFinancingAssumption {
  bank_id?: number;
  bank_name?: string;
  loan_product_id?: number;
  loan_product_name?: string;
  interest_rate: string | number;
  tenure_months: number;
  product_max_ltv_percent: string | number;
  product_max_loan_amount?: string | number;
  estimated_processing_fee: string | number;
}

export interface AffordabilityCalculateRequest {
  monthly_take_home_income: number | string;
  existing_monthly_emi?: number | string;
  available_down_payment?: number | string;
  state_id: number;
  city_id?: number | null;
  rto_id?: number | null;
  credit_score?: number;
  preferred_loan_tenure_months?: number;
  affordability_profile?: AffordabilityProfile;
  employment_type?: string;
  monthly_driving_distance?: number;
  fuel_preference?: string | null;
  body_type?: string | null;
  transmission?: string | null;
}

export interface AffordabilityBudgetBreakdown {
  affordability_profile: AffordabilityProfile;
  monthly_take_home_income: string | number;
  existing_monthly_emi: string | number;
  maximum_total_emi: string | number;
  available_car_emi: string | number;
  available_down_payment: string | number;
  maximum_affordable_loan: string | number;
  maximum_affordable_on_road_price: string | number;
  recommended_safe_budget: string | number;
  stretch_budget: string | number;
  limiting_factor: LimitingFactor;
  limiting_factor_reason: string;
  applicable_financing_assumptions: AffordabilityFinancingAssumption;
  data_status: string;
  warnings: string[];
  disclaimer: string;
}

export interface VehicleAffordabilityRequest {
  variant_id: number;
  monthly_take_home_income: number | string;
  existing_monthly_emi?: number | string;
  available_down_payment?: number | string;
  state_id: number;
  city_id?: number | null;
  rto_id?: number | null;
  credit_score?: number;
  preferred_loan_tenure_months?: number;
  affordability_profile?: AffordabilityProfile;
  down_payment_override?: number | string | null;
}

export interface VehicleAffordabilityResponse {
  variant_id: number;
  variant_name: string;
  model_name: string;
  manufacturer_name: string;
  fuel_type: string;
  transmission: string;
  ex_showroom_price: string | number;
  on_road_price: string | number;
  down_payment: string | number;
  required_loan: string | number;
  estimated_emi: string | number;
  available_car_emi: string | number;
  emi_headroom: string | number;
  affordable: boolean;
  affordability_status: AffordabilityStatus;
  affordability_rationale: string;
  limiting_factor?: LimitingFactor | null;
  selected_loan_offer?: LoanOfferItem | null;
  all_eligible_loan_offers?: LoanOfferItem[];
  data_status: string;
  disclaimer: string;
}

export interface MultiVehicleAffordabilityRequest {
  variant_ids: number[];
  monthly_take_home_income: number | string;
  existing_monthly_emi?: number | string;
  available_down_payment?: number | string;
  state_id: number;
  city_id?: number | null;
  rto_id?: number | null;
  credit_score?: number;
  preferred_loan_tenure_months?: number;
  affordability_profile?: AffordabilityProfile;
}

export interface MultiVehicleAffordabilityResponse {
  results: VehicleAffordabilityResponse[];
  total_evaluated: number;
  affordable_count: number;
  stretch_count: number;
  unaffordable_count: number;
  data_status: string;
  disclaimer: string;
}

export interface AffordabilityComparisonRequest {
  variant_ids: number[];
  monthly_take_home_income: number | string;
  existing_monthly_emi?: number | string;
  available_down_payment?: number | string;
  state_id: number;
  city_id?: number | null;
  rto_id?: number | null;
  credit_score?: number;
  preferred_loan_tenure_months?: number;
  affordability_profile?: AffordabilityProfile;
}

export interface AffordabilityComparisonResponse {
  user_budget_summary: AffordabilityBudgetBreakdown;
  vehicles: VehicleAffordabilityResponse[];
  comparison_notes: string[];
  data_status: string;
  disclaimer: string;
}

