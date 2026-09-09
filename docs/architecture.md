# CarAfford System Architecture Document

## 1. Overview
**CarAfford** is an Indian automotive affordability and on-road pricing engine. The platform empowers car buyers to make sound financial decisions by calculating exact, location-based on-road vehicle costs, determining actual loan eligibility across leading Indian banks, and calculating the Total Cost of Ownership (TCO).

---

## 2. Architectural Principles

1. **Modular Domain-Driven Design (DDD)**: Clear separation between presentation (API), business services, domain calculation engines, and persistence layers.
2. **Deterministic & Testable Calculations**: All financial (EMI, amortization, FOIR, DTI) and taxation (RTO slabs, TCS, Fastag, Cess) algorithms reside in pure domain modules without database or web framework coupling.
3. **High-Precision Financial Arithmetic**: All monetary quantities and interest rates are represented using Python's `Decimal` type to prevent binary floating-point rounding errors.
4. **Temporal Data Tracking & Auditability**: Every price, tax slab, and interest rate record tracks source attribution, effective dates, and verification timestamps.
5. **Multi-tier Scalability**: Clean async backend using FastAPI and SQLAlchemy 2.0 with PostgreSQL, prepared for Redis caching of static tax slabs and vehicle catalog data.

---

## 3. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                                  Frontend Layer                                   |
|                      Next.js (App Router) + TypeScript + Tailwind                |
|           [Affordability Form] [Car Recommendations] [TCO Breakdown Modal]         |
+------------------------------------------+----------------------------------------+
                                           | HTTP / REST (JSON)
                                           v
+-----------------------------------------------------------------------------------+
|                                  API Gateway / Routers                            |
|                            FastAPI (Thin Route Controllers)                       |
|   /api/v1/affordability  |  /api/v1/pricing  |  /api/v1/finance  |  /api/v1/vehicles |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                              Domain & Business Services                           |
|  +---------------------------+  +--------------------------+  +-----------------+  |
|  | Affordability Engine      |  | On-Road Pricing Service  |  | Recommendation  |  |
|  | - FOIR / DTI Analysis     |  | - State/RTO Tax Engine   |  |   Engine        |  |
|  | - Monthly TCO Calculation |  | - Insurance Estimator    |  | - Budget Filter |  |
|  | - Risk Index Scoring      |  | - TCS / Fastag / Cess    |  | - Multi-factor  |  |
|  +-------------+-------------+  +------------+-------------+  |   Ranking       |  |
|                |                             |                +--------+--------+  |
|                +--------------+--------------+                         |           |
|                               v                                        v           |
|  +------------------------------------------------------------------------------+  |
|  | Finance & Loan Service (EMI Math, Amortization, Bank Eligibility Slabs)      |  |
|  +------------------------------------------------------------------------------+  |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                              Repository / Data Access                             |
|              SQLAlchemy 2.0 Async Repositories + Pydantic Data Contracts          |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                             Storage & Cache Infrastructure                        |
|             PostgreSQL 16 (Relational DB)  |  Redis 7 (Catalog & Slabs Cache)     |
+-----------------------------------------------------------------------------------+
```

---

## 4. Backend Modules Breakdown

### 4.1. `vehicles`
- **Responsibilities**: Manages manufacturers (OEMs), car models, body types (Hatchback, SUV, Sedan, EV), variants, fuel types (Petrol, Diesel, CNG, Electric), transmission, safety ratings (Bharat NCAP / Global NCAP), and fuel economy (ARAI km/l or km/kWh).

### 4.2. `locations`
- **Responsibilities**: State, city, and RTO office hierarchy in India. Supports standard state registrations and special BH (Bharat Series) registrations.

### 4.3. `pricing`
- **Responsibilities**: State/City-level ex-showroom prices and historical pricing trends.

### 4.4. `taxes`
- **Tax Calculation Rules**:
  - **State RTO Tax**: Progressive percentage brackets based on fuel type (Petrol/Diesel/CNG/EV) and ex-showroom price thresholds (e.g. <₹10L, ₹10L-₹20L, >₹20L).
  - **TCS (Tax Collected at Source)**: 1% mandatory under Section 206C(1F) for motor vehicles with ex-showroom exceeding ₹10,00,000.
  - **Registration / Fastag / Cess**: Fastag fee (₹500-₹600), Hypothecation fee (₹1,500 for financed cars), State Road Safety Cess, Municipal charges.

### 4.5. `finance`
- **Responsibilities**: Bank catalog (SBI, HDFC, ICICI, etc.), loan products, interest rate tiers indexed to CIBIL credit score bands (e.g., 750+, 700-749, <700).
- **Core Math**:
  - Exact EMI Formula:
    $$EMI = P \times r \times \frac{(1+r)^n}{(1+r)^n - 1}$$
    where $P$ = principal loan amount, $r$ = monthly interest rate ($AnnualRate / 12 / 100$), $n$ = tenure in months.
  - Inverse Maximum Affordable Loan:
    $$P_{max} = EMI_{budget} \times \frac{(1+r)^n - 1}{r \times (1+r)^n}$$

### 4.6. `insurance`
- **Responsibilities**: Comprehensive Indian car insurance estimator:
  - 1-Year Own Damage (OD) based on Insured Declared Value (IDV) and engine displacement (Sub-1000cc, 1000-1500cc, >1500cc).
  - 3-Year Mandatory Third-Party (TP) statutory tariff rates (IRDAI regulated).
  - Zero-Depreciation and engine protection add-ons.

### 4.7. `affordability`
- **FOIR / DTI Standard**: Banking standard Fixed Obligation to Income Ratio. Maximum total EMI allocation capped at 40% - 50% of net take-home salary.
- **Available Car EMI Budget**:
  $$EMI_{max} = (\text{Take-Home Income} \times \text{FOIR\_LIMIT}) - \text{Existing EMIs}$$
- **Total Cost of Ownership (TCO)**:
  $$\text{Monthly TCO} = EMI + \text{Monthly Fuel} + \text{Monthly Insurance Amortized} + \text{Scheduled Maintenance}$$
  where $\text{Monthly Fuel} = \frac{\text{Monthly Commute (km)}}{\text{Variant Mileage (km/l)}} \times \text{Fuel Price (₹/l)}$.
- **Affordability Risk Score**:
  - **Comfortable**: Total Car TCO $\le$ 20% of net income
  - **Balanced**: Total Car TCO 21% – 30% of net income
  - **Stretch**: Total Car TCO 31% – 40% of net income
  - **High Risk / Strained**: Total Car TCO > 40% of net income

### 4.8. `recommendations`
- Multi-dimensional ranking based on affordability score, down-payment headroom, fuel economy, safety rating, and user body-type/fuel preferences.

### 4.9. `data_sources`
- Tracks data provenance, source URLs, effective dates, verification status, and audit trails for compliance.

---

## 5. Security and Data Integrity
- No hardcoded secrets; 100% environment-driven via Pydantic Settings.
- Input validation on all numerical limits (e.g. positive incomes, valid credit score 300–900).
- Timezone-aware UTC timestamps throughout.
