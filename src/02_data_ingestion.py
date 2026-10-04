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


EXPECTED_FILES = {
    "customers": "customers.csv",
    "quotes": "quotes.csv",
    "policies": "policies.csv",
    "claims": "claims.csv",
    "events": "events.csv"
}


# ============================================================
# HELPERS
# ============================================================

def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def load_csv(dataset_name, filename):

    file_path = RAW_DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Source file not found: {file_path}"
        )

    df = pd.read_csv(file_path)

    print(
        f"{dataset_name:<12} "
        f"{len(df):>10,} rows | "
        f"{len(df.columns):>2} columns"
    )

    return df


# ============================================================
# SOURCE FILE VALIDATION
# ============================================================

def validate_source_files():

    print_section("SOURCE FILE VALIDATION")

    missing_files = []

    for dataset_name, filename in EXPECTED_FILES.items():

        file_path = RAW_DATA_DIR / filename

        if file_path.exists():
            print(f"[OK] {filename}")
        else:
            print(f"[MISSING] {filename}")
            missing_files.append(filename)

    if missing_files:
        raise FileNotFoundError(
            f"Missing source files: {missing_files}"
        )

    print("\nAll expected source files are available.")


# ============================================================
# LOAD DATA
# ============================================================

def load_source_data():

    print_section("SOURCE DATA INGESTION")

    datasets = {}

    for dataset_name, filename in EXPECTED_FILES.items():

        datasets[dataset_name] = load_csv(
            dataset_name,
            filename
        )

    return datasets


# ============================================================
# SCHEMA VALIDATION
# ============================================================

def validate_schema(datasets):

    print_section("SCHEMA VALIDATION")

    expected_columns = {

        "customers": [
            "customer_id",
            "age",
            "gender",
            "city",
            "registration_date"
        ],

        "quotes": [
            "quote_id",
            "customer_id",
            "product_type",
            "channel",
            "quote_date",
            "premium_amount",
            "is_converted"
        ],

        "policies": [
            "policy_id",
            "quote_id",
            "customer_id",
            "product_type",
            "premium_amount",
            "policy_start_date",
            "policy_end_date",
            "policy_status"
        ],

        "claims": [
            "claim_id",
            "policy_id",
            "customer_id",
            "claim_date",
            "claim_amount",
            "claim_status"
        ],

        "events": [
            "event_id",
            "customer_id",
            "event_type",
            "device_type",
            "event_timestamp"
        ]
    }

    for dataset_name, columns in expected_columns.items():

        df = datasets[dataset_name]

        missing_columns = [
            column
            for column in columns
            if column not in df.columns
        ]

        if missing_columns:

            raise ValueError(
                f"{dataset_name} missing columns: "
                f"{missing_columns}"
            )

        print(
            f"[OK] {dataset_name:<12} "
            f"schema validated"
        )


# ============================================================
# TYPE CONVERSION
# ============================================================

def convert_data_types(datasets):

    print_section("DATA TYPE CONVERSION")

    customers = datasets["customers"]
    quotes = datasets["quotes"]
    policies = datasets["policies"]
    claims = datasets["claims"]
    events = datasets["events"]

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

    customers["age"] = pd.to_numeric(
        customers["age"],
        errors="coerce"
    )

    quotes["premium_amount"] = pd.to_numeric(
        quotes["premium_amount"],
        errors="coerce"
    )

    quotes["is_converted"] = pd.to_numeric(
        quotes["is_converted"],
        errors="coerce"
    )

    policies["premium_amount"] = pd.to_numeric(
        policies["premium_amount"],
        errors="coerce"
    )

    claims["claim_amount"] = pd.to_numeric(
        claims["claim_amount"],
        errors="coerce"
    )

    print("Date and numeric conversions completed.")

    return datasets


# ============================================================
# INITIAL DATA QUALITY PROFILE
# ============================================================

def profile_data_quality(datasets):

    print_section("INITIAL DATA QUALITY PROFILE")

    profile_rows = []

    for dataset_name, df in datasets.items():

        total_rows = len(df)

        duplicate_rows = int(
            df.duplicated().sum()
        )

        missing_values = int(
            df.isna().sum().sum()
        )

        missing_percentage = (
            missing_values
            / (total_rows * len(df.columns))
            * 100
        )

        profile_rows.append({
            "dataset": dataset_name,
            "rows": total_rows,
            "columns": len(df.columns),
            "duplicate_rows": duplicate_rows,
            "missing_values": missing_values,
            "missing_percentage": round(
                missing_percentage,
                4
            )
        })

    profile_df = pd.DataFrame(profile_rows)

    print(profile_df.to_string(index=False))

    return profile_df


# ============================================================
# PRIMARY KEY CHECK
# ============================================================

def primary_key_check(datasets):

    print_section("PRIMARY KEY QUALITY CHECK")

    primary_keys = {
        "customers": "customer_id",
        "quotes": "quote_id",
        "policies": "policy_id",
        "claims": "claim_id",
        "events": "event_id"
    }

    results = []

    for dataset_name, primary_key in primary_keys.items():

        df = datasets[dataset_name]

        missing_keys = int(
            df[primary_key].isna().sum()
        )

        duplicate_keys = int(
            df[primary_key].duplicated().sum()
        )

        unique_keys = int(
            df[primary_key].nunique()
        )

        print(
            f"{dataset_name:<12} | "
            f"PK: {primary_key:<12} | "
            f"Missing: {missing_keys:<4} | "
            f"Duplicates: {duplicate_keys:<4} | "
            f"Unique: {unique_keys:,}"
        )

        results.append({
            "dataset": dataset_name,
            "primary_key": primary_key,
            "missing_keys": missing_keys,
            "duplicate_keys": duplicate_keys,
            "unique_keys": unique_keys
        })

    return pd.DataFrame(results)


# ============================================================
# REFERENTIAL INTEGRITY
# ============================================================

def referential_integrity_check(datasets):

    print_section("REFERENTIAL INTEGRITY CHECK")

    customers = datasets["customers"]
    quotes = datasets["quotes"]
    policies = datasets["policies"]
    claims = datasets["claims"]
    events = datasets["events"]

    customer_ids = set(
        customers["customer_id"].dropna()
    )

    quote_ids = set(
        quotes["quote_id"].dropna()
    )

    policy_ids = set(
        policies["policy_id"].dropna()
    )

    checks = []

    relationships = [
        (
            "quotes.customer_id",
            quotes["customer_id"],
            customer_ids
        ),
        (
            "policies.customer_id",
            policies["customer_id"],
            customer_ids
        ),
        (
            "policies.quote_id",
            policies["quote_id"],
            quote_ids
        ),
        (
            "claims.customer_id",
            claims["customer_id"],
            customer_ids
        ),
        (
            "claims.policy_id",
            claims["policy_id"],
            policy_ids
        ),
        (
            "events.customer_id",
            events["customer_id"],
            customer_ids
        )
    ]

    for relationship_name, child_values, parent_values in relationships:

        orphan_mask = (
            ~child_values.isin(parent_values)
            & child_values.notna()
        )

        orphan_count = int(
            orphan_mask.sum()
        )

        status = (
            "OK"
            if orphan_count == 0
            else "FAILED"
        )

        print(
            f"[{status}] "
            f"{relationship_name:<25} "
            f"orphan records: {orphan_count:,}"
        )

        checks.append({
            "relationship": relationship_name,
            "orphan_records": orphan_count,
            "status": status
        })

    return pd.DataFrame(checks)


# ============================================================
# INGESTION METADATA
# ============================================================

def create_ingestion_metadata(datasets):

    print_section("INGESTION METADATA")

    ingestion_timestamp = datetime.now()

    metadata_rows = []

    for dataset_name, df in datasets.items():

        metadata_rows.append({
            "dataset_name": dataset_name,
            "source_system": "synthetic_insurance_platform",
            "source_layer": "raw_csv",
            "row_count": len(df),
            "column_count": len(df.columns),
            "ingestion_timestamp": ingestion_timestamp
        })

    metadata_df = pd.DataFrame(
        metadata_rows
    )

    print(
        metadata_df.to_string(
            index=False
        )
    )

    return metadata_df


# ============================================================
# SAVE INGESTION OUTPUTS
# ============================================================

def save_outputs(
    profile_df,
    primary_key_df,
    integrity_df,
    metadata_df
):

    print_section("SAVE INGESTION OUTPUTS")

    output_files = {
        "data_quality_profile.csv":
            profile_df,

        "primary_key_check.csv":
            primary_key_df,

        "referential_integrity_check.csv":
            integrity_df,

        "ingestion_metadata.csv":
            metadata_df
    }

    for filename, df in output_files.items():

        file_path = (
            PROCESSED_DATA_DIR
            / filename
        )

        df.to_csv(
            file_path,
            index=False
        )

        print(
            f"Saved: {file_path}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("INSURANCE DATA ENGINEERING PLATFORM - DATA INGESTION")
    print("=" * 80)

    validate_source_files()

    datasets = load_source_data()

    validate_schema(
        datasets
    )

    datasets = convert_data_types(
        datasets
    )

    profile_df = profile_data_quality(
        datasets
    )

    primary_key_df = primary_key_check(
        datasets
    )

    integrity_df = referential_integrity_check(
        datasets
    )

    metadata_df = create_ingestion_metadata(
        datasets
    )

    save_outputs(
        profile_df,
        primary_key_df,
        integrity_df,
        metadata_df
    )

    print_section("FINAL INGESTION CHECK")

    total_records = sum(
        len(df)
        for df in datasets.values()
    )

    print(
        f"Datasets ingested: "
        f"{len(datasets)}"
    )

    print(
        f"Total records processed: "
        f"{total_records:,}"
    )

    print(
        "Schema validation: COMPLETED"
    )

    print(
        "Primary key validation: COMPLETED"
    )

    print(
        "Referential integrity validation: COMPLETED"
    )

    print("\n" + "=" * 80)
    print("DATA INGESTION COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()