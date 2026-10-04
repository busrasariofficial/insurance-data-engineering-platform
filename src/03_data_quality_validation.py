from pathlib import Path
from datetime import datetime
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def load_data():

    print_section("LOAD RAW DATA")

    datasets = {
        "customers": pd.read_csv(RAW_DATA_DIR / "customers.csv"),
        "quotes": pd.read_csv(RAW_DATA_DIR / "quotes.csv"),
        "policies": pd.read_csv(RAW_DATA_DIR / "policies.csv"),
        "claims": pd.read_csv(RAW_DATA_DIR / "claims.csv"),
        "events": pd.read_csv(RAW_DATA_DIR / "events.csv")
    }

    for name, df in datasets.items():
        print(f"{name:<12}: {len(df):>10,} rows")

    return datasets


# ============================================================
# DATA QUALITY RESULT STORAGE
# ============================================================

quality_results = []


def add_result(
    dataset,
    rule,
    failed_records,
    total_records,
    severity="ERROR"
):

    failure_rate = (
        failed_records / total_records * 100
        if total_records > 0
        else 0
    )

    status = (
        "PASS"
        if failed_records == 0
        else "FAIL"
    )

    quality_results.append({
        "dataset": dataset,
        "rule": rule,
        "status": status,
        "severity": severity,
        "failed_records": int(failed_records),
        "total_records": int(total_records),
        "failure_rate_pct": round(failure_rate, 4),
        "validation_timestamp": datetime.now()
    })

    print(
        f"[{status}] "
        f"{dataset:<10} | "
        f"{rule:<45} | "
        f"Failed: {failed_records:,}"
    )


# ============================================================
# CUSTOMER VALIDATION
# ============================================================

def validate_customers(df):

    print_section("CUSTOMER DATA QUALITY RULES")

    total = len(df)

    add_result(
        "customers",
        "customer_id must not be null",
        df["customer_id"].isna().sum(),
        total
    )

    add_result(
        "customers",
        "customer_id must be unique",
        df["customer_id"].duplicated().sum(),
        total
    )

    add_result(
        "customers",
        "age must be between 18 and 100",
        (~df["age"].between(18, 100)).sum(),
        total
    )

    add_result(
        "customers",
        "gender must be Female or Male",
        (~df["gender"].isin(["Female", "Male"])).sum(),
        total
    )

    add_result(
        "customers",
        "city must not be null",
        df["city"].isna().sum(),
        total,
        severity="WARNING"
    )


# ============================================================
# QUOTE VALIDATION
# ============================================================

def validate_quotes(df, customers):

    print_section("QUOTE DATA QUALITY RULES")

    total = len(df)

    add_result(
        "quotes",
        "quote_id must not be null",
        df["quote_id"].isna().sum(),
        total
    )

    add_result(
        "quotes",
        "quote_id must be unique",
        df["quote_id"].duplicated().sum(),
        total
    )

    add_result(
        "quotes",
        "customer_id must exist in customers",
        (
            ~df["customer_id"].isin(
                customers["customer_id"]
            )
        ).sum(),
        total
    )

    add_result(
        "quotes",
        "premium_amount must not be null",
        df["premium_amount"].isna().sum(),
        total
    )

    add_result(
        "quotes",
        "premium_amount must be positive",
        (
            df["premium_amount"].notna()
            & (df["premium_amount"] <= 0)
        ).sum(),
        total
    )

    add_result(
        "quotes",
        "is_converted must be 0 or 1",
        (~df["is_converted"].isin([0, 1])).sum(),
        total
    )

    valid_products = [
        "Motor",
        "Health",
        "Home",
        "Travel"
    ]

    add_result(
        "quotes",
        "product_type must be valid",
        (~df["product_type"].isin(valid_products)).sum(),
        total
    )

    valid_channels = [
        "Web",
        "Mobile",
        "Call Center"
    ]

    add_result(
        "quotes",
        "channel must be valid",
        (~df["channel"].isin(valid_channels)).sum(),
        total
    )


# ============================================================
# POLICY VALIDATION
# ============================================================

def validate_policies(df, customers, quotes):

    print_section("POLICY DATA QUALITY RULES")

    total = len(df)

    start_date = pd.to_datetime(
        df["policy_start_date"],
        errors="coerce"
    )

    end_date = pd.to_datetime(
        df["policy_end_date"],
        errors="coerce"
    )

    add_result(
        "policies",
        "policy_id must be unique",
        df["policy_id"].duplicated().sum(),
        total
    )

    add_result(
        "policies",
        "customer_id must exist in customers",
        (
            ~df["customer_id"].isin(
                customers["customer_id"]
            )
        ).sum(),
        total
    )

    add_result(
        "policies",
        "quote_id must exist in quotes",
        (
            ~df["quote_id"].isin(
                quotes["quote_id"]
            )
        ).sum(),
        total
    )

    add_result(
        "policies",
        "policy_end_date must be after start_date",
        (end_date <= start_date).sum(),
        total
    )

    add_result(
        "policies",
        "premium_amount must be positive",
        (
            df["premium_amount"].isna()
            | (df["premium_amount"] <= 0)
        ).sum(),
        total
    )

    valid_statuses = [
        "Active",
        "Expired",
        "Cancelled"
    ]

    add_result(
        "policies",
        "policy_status must be valid",
        (~df["policy_status"].isin(valid_statuses)).sum(),
        total
    )


# ============================================================
# CLAIM VALIDATION
# ============================================================

def validate_claims(df, customers, policies):

    print_section("CLAIM DATA QUALITY RULES")

    total = len(df)

    add_result(
        "claims",
        "claim_id must be unique",
        df["claim_id"].duplicated().sum(),
        total
    )

    add_result(
        "claims",
        "policy_id must exist in policies",
        (
            ~df["policy_id"].isin(
                policies["policy_id"]
            )
        ).sum(),
        total
    )

    add_result(
        "claims",
        "customer_id must exist in customers",
        (
            ~df["customer_id"].isin(
                customers["customer_id"]
            )
        ).sum(),
        total
    )

    add_result(
        "claims",
        "claim_amount must be positive",
        (
            df["claim_amount"].isna()
            | (df["claim_amount"] <= 0)
        ).sum(),
        total
    )

    valid_statuses = [
        "Approved",
        "Rejected",
        "Pending"
    ]

    add_result(
        "claims",
        "claim_status must be valid",
        (~df["claim_status"].isin(valid_statuses)).sum(),
        total
    )


# ============================================================
# EVENT VALIDATION
# ============================================================

def validate_events(df, customers):

    print_section("EVENT DATA QUALITY RULES")

    total = len(df)

    add_result(
        "events",
        "event_id must be unique",
        df["event_id"].duplicated().sum(),
        total
    )

    add_result(
        "events",
        "customer_id must exist in customers",
        (
            ~df["customer_id"].isin(
                customers["customer_id"]
            )
        ).sum(),
        total
    )

    valid_events = [
        "page_view",
        "quote_started",
        "quote_completed",
        "policy_viewed",
        "login"
    ]

    add_result(
        "events",
        "event_type must be valid",
        (~df["event_type"].isin(valid_events)).sum(),
        total
    )

    valid_devices = [
        "Desktop",
        "Mobile",
        "Tablet"
    ]

    add_result(
        "events",
        "device_type must be valid",
        (~df["device_type"].isin(valid_devices)).sum(),
        total
    )


# ============================================================
# CLEANING / REMEDIATION
# ============================================================

def clean_data(datasets):

    print_section("DATA QUALITY REMEDIATION")

    customers = datasets["customers"].copy()
    quotes = datasets["quotes"].copy()
    policies = datasets["policies"].copy()
    claims = datasets["claims"].copy()
    events = datasets["events"].copy()

    # Customers - missing city
    missing_city_before = customers["city"].isna().sum()

    customers["city"] = customers["city"].fillna(
        "Unknown"
    )

    print(
        f"Customer missing cities repaired: "
        f"{missing_city_before:,}"
    )

    # Quotes - duplicate IDs
    duplicate_quotes_before = (
        quotes["quote_id"].duplicated().sum()
    )

    quotes = quotes.drop_duplicates(
        subset=["quote_id"],
        keep="first"
    ).copy()

    print(
        f"Duplicate quotes removed: "
        f"{duplicate_quotes_before:,}"
    )

    # Quotes - missing premiums
    missing_premium_before = (
        quotes["premium_amount"].isna().sum()
    )

    premium_medians = (
        quotes
        .groupby("product_type")["premium_amount"]
        .median()
    )

    global_premium_median = (
        quotes["premium_amount"].median()
    )

    quotes["premium_amount"] = quotes.apply(
        lambda row:
            premium_medians.get(
                row["product_type"],
                global_premium_median
            )
            if pd.isna(row["premium_amount"])
            else row["premium_amount"],
        axis=1
    )

    print(
        f"Missing quote premiums repaired: "
        f"{missing_premium_before:,}"
    )

    # Datetime conversion
    customers["registration_date"] = pd.to_datetime(
        customers["registration_date"],
        errors="coerce"
    )

    quotes["quote_date"] = pd.to_datetime(
        quotes["quote_date"],
        errors="coerce"
    )

    policies["policy_start_date"] = pd.to_datetime(
        policies["policy_start_date"],
        errors="coerce"
    )

    policies["policy_end_date"] = pd.to_datetime(
        policies["policy_end_date"],
        errors="coerce"
    )

    claims["claim_date"] = pd.to_datetime(
        claims["claim_date"],
        errors="coerce"
    )

    events["event_timestamp"] = pd.to_datetime(
        events["event_timestamp"],
        errors="coerce"
    )

    return {
        "customers": customers,
        "quotes": quotes,
        "policies": policies,
        "claims": claims,
        "events": events
    }


# ============================================================
# POST-CLEANING VALIDATION
# ============================================================

def validate_cleaned_data(datasets):

    print_section("POST-CLEANING VALIDATION")

    customers = datasets["customers"]
    quotes = datasets["quotes"]

    checks = {
        "Missing customer cities":
            int(customers["city"].isna().sum()),

        "Duplicate quote IDs":
            int(quotes["quote_id"].duplicated().sum()),

        "Missing quote premiums":
            int(quotes["premium_amount"].isna().sum())
    }

    for rule, failed in checks.items():

        status = "PASS" if failed == 0 else "FAIL"

        print(
            f"[{status}] "
            f"{rule:<35} "
            f"Remaining: {failed:,}"
        )

    return checks


# ============================================================
# SAVE CLEAN DATA
# ============================================================

def save_clean_data(datasets):

    print_section("SAVE CLEAN DATA")

    for name, df in datasets.items():

        output_path = (
            PROCESSED_DATA_DIR
            / f"{name}_clean.csv"
        )

        df.to_csv(
            output_path,
            index=False
        )

        print(
            f"{name:<12} -> "
            f"{len(df):>10,} rows"
        )


# ============================================================
# QUALITY REPORT
# ============================================================

def save_quality_report():

    print_section("DATA QUALITY REPORT")

    quality_df = pd.DataFrame(
        quality_results
    )

    output_path = (
        PROCESSED_DATA_DIR
        / "data_quality_validation_report.csv"
    )

    quality_df.to_csv(
        output_path,
        index=False
    )

    total_rules = len(quality_df)

    passed_rules = (
        quality_df["status"] == "PASS"
    ).sum()

    failed_rules = (
        quality_df["status"] == "FAIL"
    ).sum()

    error_failures = (
        (quality_df["status"] == "FAIL")
        & (quality_df["severity"] == "ERROR")
    ).sum()

    warning_failures = (
        (quality_df["status"] == "FAIL")
        & (quality_df["severity"] == "WARNING")
    ).sum()

    print(f"Validation rules: {total_rules}")
    print(f"Passed rules:     {passed_rules}")
    print(f"Failed rules:     {failed_rules}")
    print(f"Error failures:   {error_failures}")
    print(f"Warning failures: {warning_failures}")

    print("\nReport saved to:")
    print(output_path)

    return quality_df


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("INSURANCE DATA ENGINEERING PLATFORM - DATA QUALITY")
    print("=" * 80)

    datasets = load_data()

    validate_customers(
        datasets["customers"]
    )

    validate_quotes(
        datasets["quotes"],
        datasets["customers"]
    )

    validate_policies(
        datasets["policies"],
        datasets["customers"],
        datasets["quotes"]
    )

    validate_claims(
        datasets["claims"],
        datasets["customers"],
        datasets["policies"]
    )

    validate_events(
        datasets["events"],
        datasets["customers"]
    )

    quality_df = save_quality_report()

    cleaned_datasets = clean_data(
        datasets
    )

    validate_cleaned_data(
        cleaned_datasets
    )

    save_clean_data(
        cleaned_datasets
    )

    print_section("FINAL DATA QUALITY CHECK")

    print(
        f"Quality rules executed: "
        f"{len(quality_df)}"
    )

    print(
        "\nControlled source-data issues detected and repaired:"
    )

    print(
        "- Missing customer cities"
    )

    print(
        "- Missing quote premiums"
    )

    print(
        "- Duplicate quote IDs"
    )

    print(
        "\nClean datasets created successfully."
    )

    print("\n" + "=" * 80)
    print("DATA QUALITY VALIDATION COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()