from pathlib import Path
from datetime import datetime, timedelta
import random

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

RANDOM_SEED = 42

N_CUSTOMERS = 10_000
N_QUOTES = 50_000
N_POLICIES = 12_000
N_CLAIMS = 4_000
N_EVENTS = 100_000

np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def random_dates(start_date, end_date, size):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    total_seconds = int((end - start).total_seconds())

    random_seconds = np.random.randint(
        0,
        total_seconds,
        size=size
    )

    return start + pd.to_timedelta(random_seconds, unit="s")


def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# ============================================================
# CUSTOMERS
# ============================================================

def generate_customers():

    print_section("GENERATING CUSTOMERS")

    customer_ids = [
        f"CUST_{i:06d}"
        for i in range(1, N_CUSTOMERS + 1)
    ]

    cities = [
        "Istanbul",
        "Ankara",
        "Izmir",
        "Bursa",
        "Antalya",
        "Adana",
        "Konya",
        "Kocaeli"
    ]

    customers = pd.DataFrame({
        "customer_id": customer_ids,

        "age": np.random.randint(
            18,
            76,
            size=N_CUSTOMERS
        ),

        "gender": np.random.choice(
            ["Female", "Male"],
            size=N_CUSTOMERS
        ),

        "city": np.random.choice(
            cities,
            size=N_CUSTOMERS,
            p=[
                0.32,
                0.18,
                0.13,
                0.09,
                0.08,
                0.07,
                0.07,
                0.06
            ]
        ),

        "registration_date": random_dates(
            "2022-01-01",
            "2026-09-30",
            N_CUSTOMERS
        )
    })

    print(f"Customers generated: {len(customers):,}")

    return customers


# ============================================================
# QUOTES
# ============================================================

def generate_quotes(customers):

    print_section("GENERATING INSURANCE QUOTES")

    product_types = [
        "Motor",
        "Health",
        "Home",
        "Travel"
    ]

    channels = [
        "Web",
        "Mobile",
        "Call Center"
    ]

    quotes = pd.DataFrame({
        "quote_id": [
            f"Q_{i:07d}"
            for i in range(1, N_QUOTES + 1)
        ],

        "customer_id": np.random.choice(
            customers["customer_id"],
            size=N_QUOTES
        ),

        "product_type": np.random.choice(
            product_types,
            size=N_QUOTES,
            p=[0.55, 0.20, 0.15, 0.10]
        ),

        "channel": np.random.choice(
            channels,
            size=N_QUOTES,
            p=[0.60, 0.25, 0.15]
        ),

        "quote_date": random_dates(
            "2025-01-01",
            "2026-09-30",
            N_QUOTES
        ),

        "premium_amount": np.round(
            np.random.lognormal(
                mean=8.0,
                sigma=0.55,
                size=N_QUOTES
            ),
            2
        )
    })

    conversion_probability = (
        0.18
        + (quotes["channel"] == "Web") * 0.04
        + (quotes["product_type"] == "Motor") * 0.03
        - (quotes["premium_amount"] > 5000) * 0.05
    )

    conversion_probability = np.clip(
        conversion_probability,
        0.05,
        0.60
    )

    quotes["is_converted"] = np.random.binomial(
        1,
        conversion_probability
    )

    print(f"Quotes generated: {len(quotes):,}")
    print(
        f"Quote conversion rate: "
        f"{quotes['is_converted'].mean():.2%}"
    )

    return quotes


# ============================================================
# POLICIES
# ============================================================

def generate_policies(quotes):

    print_section("GENERATING POLICIES")

    converted_quotes = quotes[
        quotes["is_converted"] == 1
    ].copy()

    if len(converted_quotes) >= N_POLICIES:

        selected_quotes = converted_quotes.sample(
            N_POLICIES,
            random_state=RANDOM_SEED
        )

    else:

        selected_quotes = converted_quotes.copy()

    policies = selected_quotes[
        [
            "quote_id",
            "customer_id",
            "product_type",
            "premium_amount",
            "quote_date"
        ]
    ].copy()

    policies = policies.reset_index(drop=True)

    policies["policy_id"] = [
        f"POL_{i:07d}"
        for i in range(1, len(policies) + 1)
    ]

    policies["policy_start_date"] = (
        policies["quote_date"]
        + pd.to_timedelta(
            np.random.randint(
                0,
                8,
                size=len(policies)
            ),
            unit="D"
        )
    )

    policies["policy_end_date"] = (
        policies["policy_start_date"]
        + pd.DateOffset(years=1)
    )

    policies["policy_status"] = np.random.choice(
        [
            "Active",
            "Expired",
            "Cancelled"
        ],
        size=len(policies),
        p=[0.70, 0.22, 0.08]
    )

    policies = policies[
        [
            "policy_id",
            "quote_id",
            "customer_id",
            "product_type",
            "premium_amount",
            "policy_start_date",
            "policy_end_date",
            "policy_status"
        ]
    ]

    print(f"Policies generated: {len(policies):,}")

    return policies


# ============================================================
# CLAIMS
# ============================================================

def generate_claims(policies):

    print_section("GENERATING CLAIMS")

    selected_policies = policies.sample(
        min(N_CLAIMS, len(policies)),
        replace=False,
        random_state=RANDOM_SEED
    ).reset_index(drop=True)

    claim_dates = (
        selected_policies["policy_start_date"]
        + pd.to_timedelta(
            np.random.randint(
                1,
                300,
                size=len(selected_policies)
            ),
            unit="D"
        )
    )

    claims = pd.DataFrame({
        "claim_id": [
            f"CLM_{i:07d}"
            for i in range(1, len(selected_policies) + 1)
        ],

        "policy_id":
            selected_policies["policy_id"],

        "customer_id":
            selected_policies["customer_id"],

        "claim_date":
            claim_dates,

        "claim_amount":
            np.round(
                np.random.lognormal(
                    mean=8.3,
                    sigma=0.8,
                    size=len(selected_policies)
                ),
                2
            ),

        "claim_status":
            np.random.choice(
                [
                    "Approved",
                    "Rejected",
                    "Pending"
                ],
                size=len(selected_policies),
                p=[0.72, 0.18, 0.10]
            )
    })

    print(f"Claims generated: {len(claims):,}")

    return claims


# ============================================================
# USER EVENTS
# ============================================================

def generate_events(customers):

    print_section("GENERATING USER EVENTS")

    event_types = [
        "page_view",
        "quote_started",
        "quote_completed",
        "policy_viewed",
        "login"
    ]

    device_types = [
        "Desktop",
        "Mobile",
        "Tablet"
    ]

    events = pd.DataFrame({
        "event_id": [
            f"EVT_{i:08d}"
            for i in range(1, N_EVENTS + 1)
        ],

        "customer_id":
            np.random.choice(
                customers["customer_id"],
                size=N_EVENTS
            ),

        "event_type":
            np.random.choice(
                event_types,
                size=N_EVENTS,
                p=[
                    0.45,
                    0.18,
                    0.12,
                    0.10,
                    0.15
                ]
            ),

        "device_type":
            np.random.choice(
                device_types,
                size=N_EVENTS,
                p=[0.42, 0.53, 0.05]
            ),

        "event_timestamp":
            random_dates(
                "2026-01-01",
                "2026-09-30",
                N_EVENTS
            )
    })

    print(f"Events generated: {len(events):,}")

    return events


# ============================================================
# DATA QUALITY ISSUES
# ============================================================

def inject_data_quality_issues(customers, quotes):

    print_section("INJECTING CONTROLLED DATA QUALITY ISSUES")

    customers = customers.copy()
    quotes = quotes.copy()

    # Missing city values
    missing_city_idx = np.random.choice(
        customers.index,
        size=50,
        replace=False
    )

    customers.loc[
        missing_city_idx,
        "city"
    ] = np.nan

    # Missing premium values
    missing_premium_idx = np.random.choice(
        quotes.index,
        size=100,
        replace=False
    )

    quotes.loc[
        missing_premium_idx,
        "premium_amount"
    ] = np.nan

    # Duplicate quote records
    duplicate_quotes = quotes.sample(
        25,
        random_state=RANDOM_SEED
    )

    quotes = pd.concat(
        [
            quotes,
            duplicate_quotes
        ],
        ignore_index=True
    )

    print("Injected issues:")
    print("- 50 missing customer cities")
    print("- 100 missing quote premiums")
    print("- 25 duplicate quote records")

    return customers, quotes


# ============================================================
# SAVE DATA
# ============================================================

def save_dataset(df, filename):

    file_path = RAW_DATA_DIR / filename

    df.to_csv(
        file_path,
        index=False
    )

    print(
        f"{filename:<20} -> "
        f"{len(df):>8,} rows"
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("=" * 80)
    print("INSURANCE DATA ENGINEERING PLATFORM")
    print("SYNTHETIC SOURCE DATA GENERATION")
    print("=" * 80)

    customers = generate_customers()

    quotes = generate_quotes(
        customers
    )

    policies = generate_policies(
        quotes
    )

    claims = generate_claims(
        policies
    )

    events = generate_events(
        customers
    )

    customers, quotes = inject_data_quality_issues(
        customers,
        quotes
    )

    print_section("SAVING RAW SOURCE DATA")

    save_dataset(
        customers,
        "customers.csv"
    )

    save_dataset(
        quotes,
        "quotes.csv"
    )

    save_dataset(
        policies,
        "policies.csv"
    )

    save_dataset(
        claims,
        "claims.csv"
    )

    save_dataset(
        events,
        "events.csv"
    )

    print_section("FINAL DATASET SUMMARY")

    print(
        f"Customers : {len(customers):,}"
    )

    print(
        f"Quotes    : {len(quotes):,}"
    )

    print(
        f"Policies  : {len(policies):,}"
    )

    print(
        f"Claims    : {len(claims):,}"
    )

    print(
        f"Events    : {len(events):,}"
    )

    print("\nRaw data directory:")
    print(RAW_DATA_DIR)

    print("\n" + "=" * 80)
    print("SOURCE DATA GENERATION COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()