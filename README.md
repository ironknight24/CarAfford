# CarAfford - Indian Car Affordability & On-Road Price Recommendation Engine

[![Tests](https://img.shields.io/badge/tests-23%20passed-emerald)](./backend/tests)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./backend)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-teal)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15%20App%20Router-black)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://postgresql.org)

**CarAfford** is a production-grade web application tailored specifically for Indian car buyers. It evaluates monthly take-home salary, existing debts, available down payment, registration State/RTO, CIBIL score, and driving habits to calculate exact on-road prices, loan eligibility across major Indian banks, and ranks matching cars based on realistic monthly Total Cost of Ownership (TCO).

---

## 🚀 Key Features

1. **State & RTO Specific Taxation Engine**:
   - Progressive road tax slabs across Indian states (Delhi, Maharashtra, Karnataka, Tamil Nadu, Uttar Pradesh, etc.).
   - Support for **BH (Bharat) Series** registrations.
   - 1% TCS (Tax Collected at Source) under Section 206C(1F) for vehicles with ex-showroom > ₹10 Lakhs.
   - FASTag, Registration fees, Hypothecation, and State Green Cess.

2. **Bank Auto Loan & EMI Engine**:
   - High-precision `Decimal` financial arithmetic.
   - Tiered interest rate pricing based on CIBIL credit score bands (SBI, HDFC, ICICI, Bank of Baroda).
   - Monthly amortization schedule generation and inverse maximum loan calculation.

3. **Total Cost of Ownership (TCO) & FOIR Scoring**:
   - Fixed Obligation to Income Ratio (FOIR) calculation (default 40% banking limit).
   - Real-world fuel cost estimation (Petrol, Diesel, CNG, Electric).
   - 1-Year Own Damage + 3-Year Third-Party statutory IRDAI insurance estimation + Zero-Depreciation addon.
   - Affordability scoring (0-100 scale) and categorization (`Comfortable`, `Balanced`, `Stretch`, `Risky`).

4. **Multi-Factor Recommendation Engine**:
   - Matches and ranks Indian car catalog models against buyer budget and lifestyle constraints.
   - Filters by Body Type (SUV, Hatchback, Sedan), Fuel (Petrol, Diesel, CNG, EV), and Safety Ratings (Bharat NCAP / Global NCAP).

5. **Data Provenance & Freshness Tracking**:
   - Every price, tax slab, and interest rate record tracks source attribution, source URL, effective date, and verification timestamps.

---

## 🏗️ Repository Structure

```
carafford/
├── backend/                  # FastAPI + SQLAlchemy 2.0 Async + Alembic
│   ├── app/
│   │   ├── api/v1/           # Thin REST controllers (locations, vehicles, pricing, finance, affordability)
│   │   ├── core/             # Settings, DB engines, redis client, custom exceptions
│   │   ├── models/           # SQLAlchemy 2.0 Declarative Models
│   │   ├── repositories/     # Data access layer (Vehicle, Location, Finance, Pricing)
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── services/         # Pure domain computational services (Tax, Finance, Insurance, Affordability, Recs)
│   │   └── main.py           # FastAPI entrypoint
│   ├── alembic/              # Database migration scripts
│   ├── tests/                # Pytest unit and integration test suite
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                 # Next.js App Router (TypeScript + Tailwind CSS)
│   ├── src/
│   │   ├── app/              # Next.js App Router pages (Home, Explore)
│   │   ├── components/       # UI components (AffordabilityForm, BudgetSummary, CarCard, Modal)
│   │   ├── lib/              # API client & INR currency formatting utilities
│   │   └── types/            # TypeScript interfaces
│   ├── Dockerfile
│   └── package.json
├── infrastructure/           # Docker Compose configurations
│   ├── docker-compose.yml    # Full stack production Compose (Postgres, Redis, Backend, Frontend)
│   └── docker-compose.dev.yml# Dev helper Compose (Postgres, Redis)
├── docs/                     # Architecture & API specifications
│   ├── architecture.md
│   └── api_spec.md
├── scripts/                  # Helper CLI scripts
│   ├── run_dev.sh            # One-command development launcher
│   ├── run_tests.sh          # Full test suite runner
│   └── seed_data.py          # Database seed script
├── .env.example
└── README.md
```

---

## 🛠️ Quickstart & Local Setup

### Prerequisites
- **Python 3.12+**
- **Node.js 20+**
- **Docker & Docker Compose** (optional for local containers)

### 1. Clone and Configure Environment
```bash
cp .env.example .env
```

### 2. Run with Docker Compose (Recommended)
To launch all services (PostgreSQL, Redis, Backend, Frontend) with a single command:
```bash
docker compose -f infrastructure/docker-compose.yml up --build
```
- **Frontend App**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 3. Local Development (Without Full Docker)

#### Backend Setup:
```bash
# 1. Create and activate virtualenv
python3 -m venv backend/.venv
source backend/.venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements-dev.txt

# 3. Start database support container
docker compose -f infrastructure/docker-compose.dev.yml up -d

# 4. Run database migrations & seed initial catalog data
cd backend
alembic upgrade head
python ../scripts/seed_data.py

# 5. Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Running Tests

CarAfford comes with a comprehensive Pytest test suite covering pure financial math, state tax rules, FOIR constraints, and API integration flows:

```bash
# Run backend test suite
./scripts/run_tests.sh

# Or directly with pytest
PYTHONPATH=backend ./backend/.venv/bin/pytest -v backend/tests/
```

---

## 📐 Indian Taxation & Financial Calculations

### Exact Standard EMI
$$EMI = P \times r \times \frac{(1+r)^n}{(1+r)^n - 1}$$
where $P$ = principal loan amount, $r = \frac{AnnualRate}{1200}$, $n$ = tenure in months.

### Max Affordable Loan (Inverse EMI)
$$P_{max} = EMI_{budget} \times \frac{(1+r)^n - 1}{r \times (1+r)^n}$$

### Monthly Total Cost of Ownership (TCO)
$$TCO = EMI + \text{Monthly Fuel} + \frac{\text{Annual Insurance}}{12} + \frac{\text{ExShowroom} \times 1.5\%}{12}$$

For detailed calculation formulas, refer to [docs/api_spec.md](docs/api_spec.md) and [docs/architecture.md](docs/architecture.md).
