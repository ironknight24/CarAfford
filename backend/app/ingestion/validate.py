import argparse
import asyncio
from decimal import Decimal
from app.ingestion.validators.vehicle_validator import VehicleDataValidator
from app.ingestion.validators.pricing_validator import PriceDataValidator
from app.ingestion.validators.tax_validator import TaxRuleDataValidator
from app.ingestion.validators.finance_validator import FinanceDataValidator


def main():
    parser = argparse.ArgumentParser(description="CarAfford Ingestion Dataset Validator")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        choices=["vehicles", "prices", "taxes", "finance"],
        help="Dataset validator to run",
    )
    args = parser.parse_args()

    print(f"🔍 Running validator for dataset: {args.dataset}...")

    if args.dataset == "vehicles":
        validator = VehicleDataValidator()
        sample = {
            "manufacturer_name": "Tata Motors",
            "model_name": "Punch",
            "variant_name": "Punch Pure 1.2 MT",
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "body_type": "SUV",
            "seating_capacity": 5,
            "arai_mileage_kmpl": Decimal("20.09"),
            "safety_rating_stars": 5,
            "airbags_count": 2,
        }
    elif args.dataset == "prices":
        validator = PriceDataValidator()
        sample = {
            "ex_showroom_price": Decimal("612900.00"),
            "effective_from": "2026-01-01T00:00:00Z",
        }
    elif args.dataset == "taxes":
        validator = TaxRuleDataValidator()
        sample = {
            "state_code": "KA",
            "tax_type": "ROAD_TAX",
            "calculation_type": "PERCENTAGE",
            "base_rate_percent": Decimal("14.0"),
        }
    else:
        validator = FinanceDataValidator()
        sample = {
            "bank_name": "SBI",
            "product_name": "Car Loan",
            "annual_interest_rate": Decimal("8.75"),
            "min_cibil_score": 700,
            "max_cibil_score": 850,
        }

    is_valid, errors = validator.validate(sample)
    if is_valid:
        print(f"✅ Sample item for dataset '{args.dataset}' passed all validation rules!")
    else:
        print(f"❌ Validation errors for '{args.dataset}': {errors}")


if __name__ == "__main__":
    main()
