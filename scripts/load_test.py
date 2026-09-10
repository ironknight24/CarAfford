#!/usr/bin/env python3
"""CarAfford Production Performance & Load Testing Suite
Evaluates baseline and concurrent performance under representative workloads (10, 25, 50 concurrent requests).
Measures p50, p95, p99 latency percentiles and error rates.
"""

import asyncio
import statistics
import time
from typing import Any, Dict, List
import httpx

API_BASE_URL = "http://localhost:8000/api/v1"

# Representative workloads
WORKLOADS = [
    {
        "name": "Affordability Calculation",
        "method": "POST",
        "url": f"{API_BASE_URL}/affordability/calculate",
        "json": {
            "monthly_take_home_income": 120000,
            "existing_monthly_emi": 15000,
            "available_down_payment": 250000,
            "state_id": 1,
            "city_id": 1,
            "credit_score": 780,
            "preferred_loan_tenure_months": 60,
            "affordability_profile": "BALANCED",
        },
    },
    {
        "name": "Vehicle Recommendations",
        "method": "POST",
        "url": f"{API_BASE_URL}/recommendations",
        "json": {
            "monthly_take_home_income": 120000,
            "existing_monthly_emis": 15000,
            "available_down_payment": 250000,
            "state_id": 1,
            "city_id": 1,
            "cibil_score": 780,
            "desired_tenure_months": 60,
            "affordability_profile": "BALANCED",
        },
    },
    {
        "name": "TCO Calculation",
        "method": "POST",
        "url": f"{API_BASE_URL}/tco/calculate",
        "json": {
            "state_id": 1,
            "city_id": 1,
            "monthly_driving_distance_km": 1200,
            "down_payment": 200000,
            "credit_score": 750,
            "preferred_loan_tenure_months": 60,
            "fuel_type": "Petrol",
        },
    },
    {
        "name": "On-Road Pricing Calculation",
        "method": "POST",
        "url": f"{API_BASE_URL}/pricing/on-road",
        "json": {
            "variant_id": 1,
            "state_id": 1,
            "is_bh_series": False,
            "include_zero_dep_insurance": True,
            "is_financed": True,
        },
    },
]


async def make_request(client: httpx.AsyncClient, workload: Dict[str, Any]) -> Tuple[float, int, bool]:
    t0 = time.perf_counter()
    try:
        res = await client.request(
            method=workload["method"],
            url=workload["url"],
            json=workload.get("json"),
            timeout=15.0,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        success = res.status_code in [200, 201]
        return duration_ms, res.status_code, success
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        return duration_ms, 0, False


async def run_concurrency_batch(workload: Dict[str, Any], concurrency: int, total_requests: int) -> Dict[str, Any]:
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)
    async with httpx.AsyncClient(limits=limits) as client:
        sem = asyncio.Semaphore(concurrency)

        async def worker():
            async with sem:
                return await make_request(client, workload)

        tasks = [worker() for _ in range(total_requests)]
        t_start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - t_start

    latencies = [r[0] for r in results]
    successes = sum(1 for r in results if r[2])
    error_rate = ((total_requests - successes) / total_requests) * 100

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = statistics.mean(latencies)
    rps = total_requests / total_time

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "total_time_sec": round(total_time, 2),
        "requests_per_sec": round(rps, 1),
        "success_count": successes,
        "error_rate_pct": round(error_rate, 2),
        "avg_ms": round(avg, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
    }


async def main():
    print("=" * 80)
    print("🏎️  CarAfford Performance & Load Testing Benchmark")
    print(f"Target: {API_BASE_URL}")
    print("=" * 80)

    concurrency_levels = [10, 25, 50]
    all_summary = []

    for workload in WORKLOADS:
        print(f"\n📊 Profiling Endpoint: [{workload['name']}]")
        print("-" * 80)
        print(f"{'Concurrency':<12} | {'Reqs':<6} | {'RPS':<8} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'Errors':<8}")
        print("-" * 80)

        for conc in concurrency_levels:
            total_reqs = max(conc * 4, 40)
            res = await run_concurrency_batch(workload, conc, total_reqs)
            all_summary.append({"workload": workload["name"], **res})
            print(
                f"{res['concurrency']:<12} | "
                f"{res['total_requests']:<6} | "
                f"{res['requests_per_sec']:<8} | "
                f"{res['p50_ms']:<10} | "
                f"{res['p95_ms']:<10} | "
                f"{res['p99_ms']:<10} | "
                f"{res['error_rate_pct']}%"
            )

    print("\n" + "=" * 80)
    print("✅ Performance benchmark completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    from typing import Tuple
    asyncio.run(main())
