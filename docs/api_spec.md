# CarAfford API Specification & Mathematical Formulations

## 1. Domain Mathematical Formulations

### 1.1. Equated Monthly Installment (EMI) Formula
For an auto loan with principal $P$, annual interest rate $R$ (in percentage), and tenure $n$ months:
$$\text{Monthly Interest Rate } r = \frac{R}{12 \times 100}$$
$$\text{Compounding Factor } F = (1 + r)^n$$
$$\text{Monthly EMI} = P \times r \times \frac{F}{F - 1}$$

### 1.2. Inverse Loan Capacity (Max Affordable Loan)
Given an available monthly EMI budget $EMI_{avail}$:
$$P_{max} = EMI_{avail} \times \frac{F - 1}{r \times F}$$

### 1.3. Banking FOIR / DTI Constraint
In Indian retail automotive finance:
$$\text{Max Total Allowed EMIs} = \text{Monthly Take-Home Salary} \times \text{FOIR\_LIMIT} \quad (\text{Default } 40\%)$$
$$\text{Available Car EMI Budget} = \max(0, \text{Max Total Allowed EMIs} - \text{Existing EMIs})$$

### 1.4. Indian On-Road Price Composition
$$\text{On-Road Price} = \text{Ex-Showroom} + \text{State RTO Tax} + \text{Cess} + \text{Registration Fee} + \text{FASTag} + \text{TCS} + \text{Insurance}$$
- **1% TCS**: Applicable under Section 206C(1F) when Ex-showroom exceeds ₹10,00,000.
- **BH Series Tax**: Calculated based on MoRTH brackets (8% <10L, 10% 10-20L, 12% >20L; Diesel +2%, EV -2%) payable in 2-year increments over a 15-year cycle.

### 1.5. Total Cost of Ownership (Monthly TCO)
$$\text{Monthly TCO} = EMI + \text{Monthly Fuel} + \text{Monthly Insurance Amortized} + \text{Scheduled Maintenance}$$
- $\text{Monthly Fuel} = \frac{\text{Monthly Commute (km)}}{\text{Real-World Mileage (km/l)}} \times \text{Fuel Price (₹/l)}$
- $\text{Monthly Insurance} = \frac{\text{Annual Premium}}{12}$
- $\text{Monthly Maintenance} = \frac{\text{Ex-Showroom} \times 1.5\%}{12}$

---

## 2. API Endpoints

### 2.1. Locations & Slabs
- `GET /api/v1/locations/states`
  - Returns list of all Indian States and Union Territories.
- `GET /api/v1/locations/states/{state_id}/cities`
  - Returns list of Tier 1/2 cities for selected state.
- `GET /api/v1/locations/states/{state_id}/rtos`
  - Returns RTO offices for state.

### 2.2. Vehicles & Catalog
- `GET /api/v1/vehicles/manufacturers`
  - Returns Indian OEMs (Tata, Maruti, Hyundai, Mahindra, Kia, etc.).
- `GET /api/v1/vehicles/models?manufacturer_id=...&body_type=...`
  - Returns models filtered by manufacturer or body type.
- `GET /api/v1/vehicles/variants`
  - Query parameters: `fuel_type`, `transmission`, `min_seating`, `min_safety_rating`, `search`.

### 2.3. Pricing & On-Road Calculation
- `POST /api/v1/pricing/on-road-breakdown`
  - Request body:
    ```json
    {
      "variant_id": 1,
      "state_id": 1,
      "city_id": null,
      "is_bh_series": false,
      "include_zero_dep_insurance": true,
      "is_financed": true
    }
    ```
  - Response: Full line-item breakdown (Ex-showroom, RTO Tax, Cess, Fastag, TCS, Insurance IDV, OD, TP, Zero Dep, and On-road total).

### 2.4. Finance & Eligibility
- `POST /api/v1/finance/calculate-emi?generate_schedule=true`
  - Computes monthly EMI, total interest, total repayment, and month-by-month amortization schedule.
- `POST /api/v1/finance/loan-eligibility`
  - Computes user maximum loan eligibility based on income and FOIR.

### 2.5. Affordability & Recommendation
- `POST /api/v1/recommendations`
  - Request body:
    ```json
    {
      "monthly_take_home_income": 100000.0,
      "existing_monthly_emis": 10000.0,
      "available_down_payment": 200000.0,
      "state_id": 1,
      "desired_tenure_months": 60,
      "cibil_score": 750,
      "monthly_commute_km": 1000
    }
    ```
  - Response: Comprehensive budget capacity + list of matching vehicles ranked by Affordability Score (0-100), safety rating, and TCO.
