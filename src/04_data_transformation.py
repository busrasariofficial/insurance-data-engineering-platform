from pathlib import Path
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
TRANSFORMED_DATA_DIR = PROJECT_ROOT / "data" / "transformed"

TRANSFORMED_DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# HELPERS
# ============================================================

def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# ============================================================
# LOAD CLEAN DATA
# ============================================================

def load_clean_data():

    print_section("LOAD CLEAN DATA")

    datasets = {
        "customers": pd.read_csv(
            PROCESSED_DATA_DIR / "customers_clean.csv"
        ),
        "quotes": pd.read_csv(
            PROCESSED_DATA_DIR / "quotes_clean.csv"
        ),
        "policies": pd.read_csv(
            PROCESSED_DATA_DIR / "policies_clean.csv"
        ),
        "claims": pd.read_csv(
            PROCESSED_DATA_DIR / "claims_clean.csv"
        ),
        "events": pd.read_csv(
            PROCESSED_DATA_DIR / "events_clean.csv"
        )
    }

    for name, df in datasets.items():
        print(
            f"{name:<12}: "
            f"{len(df):>10,} rows | "
            f"{len(df.columns):>2} columns"
        )

    return datasets


# ============================================================
# DATETIME CONVERSION
# ============================================================

def convert_datetime_columns(datasets):

    print_section("DATETIME STANDARDIZATION")

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

    print("Datetime columns standardized.")

    return datasets


# ============================================================
# CUSTOMER DIMENSION
# ============================================================

def create_customer_dimension(customers):

    print_section("CREATE CUSTOMER DIMENSION")

    dim_customer = customers.copy()

    dim_customer["age_group"] = pd.cut(
        dim_customer["age"],
        bins=[
            17,
            25,
            35,
            45,
            55,
            65,
            100
        ],
        labels=[
            "18-25",
            "26-35",
            "36-45",
            "46-55",
            "56-65",
            "66+"
        ]
    )

    dim_customer["registration_year"] = (
        dim_customer["registration_date"].dt.year
    )

    dim_customer["registration_month"] = (
        dim_customer["registration_date"].dt.month
    )

    dim_customer["registration_month_name"] = (
        dim_customer["registration_date"]
        .dt.month_name()
    )

    dim_customer = dim_customer[
        [
            "customer_id",
            "age",
            "age_group",
            "gender",
            "city",
            "registration_date",
            "registration_year",
            "registration_month",
            "registration_month_name"
        ]
    ].copy()

    print(
        f"Customer dimension rows: "
        f"{len(dim_customer):,}"
    )

    print(
        f"Customer dimension columns: "
        f"{len(dim_customer.columns)}"
    )

    return dim_customer


# ============================================================
# QUOTE FACT TABLE
# ============================================================

def create_quote_fact(quotes):

    print_section("CREATE QUOTE FACT TABLE")

    fact_quotes = quotes.copy()

    fact_quotes["quote_year"] = (
        fact_quotes["quote_date"].dt.year
    )

    fact_quotes["quote_month"] = (
        fact_quotes["quote_date"].dt.month
    )

    fact_quotes["quote_month_name"] = (
        fact_quotes["quote_date"].dt.month_name()
    )

    fact_quotes["quote_quarter"] = (
        fact_quotes["quote_date"].dt.quarter
    )

    fact_quotes["quote_day_of_week"] = (
        fact_quotes["quote_date"].dt.day_name()
    )

    fact_quotes["conversion_label"] = (
        fact_quotes["is_converted"]
        .map({
            0: "Not Converted",
            1: "Converted"
        })
    )

    fact_quotes["premium_band"] = pd.cut(
        fact_quotes["premium_amount"],
        bins=[
            0,
            1000,
            2500,
            5000,
            10000,
            float("inf")
        ],
        labels=[
            "0-1K",
            "1K-2.5K",
            "2.5K-5K",
            "5K-10K",
            "10K+"
        ]
    )

    print(
        f"Quote fact rows: "
        f"{len(fact_quotes):,}"
    )

    print(
        f"Converted quotes: "
        f"{int(fact_quotes['is_converted'].sum()):,}"
    )

    print(
        f"Conversion rate: "
        f"{fact_quotes['is_converted'].mean() * 100:.2f}%"
    )

    return fact_quotes


# ============================================================
# POLICY FACT TABLE
# ============================================================

def create_policy_fact(policies):

    print_section("CREATE POLICY FACT TABLE")

    fact_policies = policies.copy()

    fact_policies["policy_year"] = (
        fact_policies["policy_start_date"].dt.year
    )

    fact_policies["policy_month"] = (
        fact_policies["policy_start_date"].dt.month
    )

    fact_policies["policy_month_name"] = (
        fact_policies["policy_start_date"]
        .dt.month_name()
    )

    fact_policies["policy_duration_days"] = (
        fact_policies["policy_end_date"]
        - fact_policies["policy_start_date"]
    ).dt.days

    fact_policies["annualized_premium"] = (
        fact_policies["premium_amount"]
        / fact_policies["policy_duration_days"]
        * 365
    )

    fact_policies["is_active"] = (
        fact_policies["policy_status"]
        .eq("Active")
        .astype(int)
    )

    print(
        f"Policy fact rows: "
        f"{len(fact_policies):,}"
    )

    print(
        f"Total written premium: "
        f"{fact_policies['premium_amount'].sum():,.2f}"
    )

    print(
        f"Active policies: "
        f"{fact_policies['is_active'].sum():,}"
    )

    return fact_policies


# ============================================================
# CLAIM FACT TABLE
# ============================================================

def create_claim_fact(claims, policies):

    print_section("CREATE CLAIM FACT TABLE")

    policy_reference = policies[
        [
            "policy_id",
            "premium_amount"
        ]
    ].rename(
        columns={
            "premium_amount":
                "policy_premium_amount"
        }
    )

    fact_claims = claims.merge(
        policy_reference,
        on="policy_id",
        how="left",
        validate="many_to_one"
    )

    fact_claims["claim_year"] = (
        fact_claims["claim_date"].dt.year
    )

    fact_claims["claim_month"] = (
        fact_claims["claim_date"].dt.month
    )

    fact_claims["claim_month_name"] = (
        fact_claims["claim_date"]
        .dt.month_name()
    )

    fact_claims["claim_to_premium_ratio"] = (
        fact_claims["claim_amount"]
        / fact_claims["policy_premium_amount"]
    )

    fact_claims["is_approved"] = (
        fact_claims["claim_status"]
        .eq("Approved")
        .astype(int)
    )

    print(
        f"Claim fact rows: "
        f"{len(fact_claims):,}"
    )

    print(
        f"Total claim amount: "
        f"{fact_claims['claim_amount'].sum():,.2f}"
    )

    print(
        f"Approved claims: "
        f"{fact_claims['is_approved'].sum():,}"
    )

    return fact_claims


# ============================================================
# EVENT FACT TABLE
# ============================================================

def create_event_fact(events):

    print_section("CREATE EVENT FACT TABLE")

    fact_events = events.copy()

    fact_events["event_date"] = (
        fact_events["event_timestamp"].dt.date
    )

    fact_events["event_year"] = (
        fact_events["event_timestamp"].dt.year
    )

    fact_events["event_month"] = (
        fact_events["event_timestamp"].dt.month
    )

    fact_events["event_day"] = (
        fact_events["event_timestamp"].dt.day
    )

    fact_events["event_hour"] = (
        fact_events["event_timestamp"].dt.hour
    )

    fact_events["event_day_of_week"] = (
        fact_events["event_timestamp"].dt.day_name()
    )

    fact_events["is_mobile"] = (
        fact_events["device_type"]
        .eq("Mobile")
        .astype(int)
    )

    print(
        f"Event fact rows: "
        f"{len(fact_events):,}"
    )

    print("\nEvent distribution:")

    print(
        fact_events["event_type"]
        .value_counts()
        .to_string()
    )

    return fact_events


# ============================================================
# CUSTOMER 360 TABLE
# ============================================================

def create_customer_360(
    dim_customer,
    fact_quotes,
    fact_policies,
    fact_claims,
    fact_events
):

    print_section("CREATE CUSTOMER 360 TABLE")

    # --------------------------------------------------------
    # QUOTE AGGREGATES
    # --------------------------------------------------------

    quote_agg = (
        fact_quotes
        .groupby("customer_id")
        .agg(
            total_quotes=(
                "quote_id",
                "count"
            ),
            converted_quotes=(
                "is_converted",
                "sum"
            ),
            average_quoted_premium=(
                "premium_amount",
                "mean"
            ),
            total_quoted_premium=(
                "premium_amount",
                "sum"
            )
        )
        .reset_index()
    )

    quote_agg["customer_conversion_rate"] = (
        quote_agg["converted_quotes"]
        / quote_agg["total_quotes"]
    )

    # --------------------------------------------------------
    # POLICY AGGREGATES
    # --------------------------------------------------------

    policy_agg = (
        fact_policies
        .groupby("customer_id")
        .agg(
            total_policies=(
                "policy_id",
                "count"
            ),
            active_policies=(
                "is_active",
                "sum"
            ),
            total_policy_premium=(
                "premium_amount",
                "sum"
            ),
            average_policy_premium=(
                "premium_amount",
                "mean"
            )
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # CLAIM AGGREGATES
    # --------------------------------------------------------

    claim_agg = (
        fact_claims
        .groupby("customer_id")
        .agg(
            total_claims=(
                "claim_id",
                "count"
            ),
            approved_claims=(
                "is_approved",
                "sum"
            ),
            total_claim_amount=(
                "claim_amount",
                "sum"
            ),
            average_claim_amount=(
                "claim_amount",
                "mean"
            )
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # EVENT AGGREGATES
    # --------------------------------------------------------

    event_agg = (
        fact_events
        .groupby("customer_id")
        .agg(
            total_events=(
                "event_id",
                "count"
            ),
            mobile_events=(
                "is_mobile",
                "sum"
            ),
            last_event_timestamp=(
                "event_timestamp",
                "max"
            )
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # MERGE
    # --------------------------------------------------------

    customer_360 = (
        dim_customer
        .merge(
            quote_agg,
            on="customer_id",
            how="left"
        )
        .merge(
            policy_agg,
            on="customer_id",
            how="left"
        )
        .merge(
            claim_agg,
            on="customer_id",
            how="left"
        )
        .merge(
            event_agg,
            on="customer_id",
            how="left"
        )
    )

    numeric_fill_columns = [
        "total_quotes",
        "converted_quotes",
        "average_quoted_premium",
        "total_quoted_premium",
        "customer_conversion_rate",
        "total_policies",
        "active_policies",
        "total_policy_premium",
        "average_policy_premium",
        "total_claims",
        "approved_claims",
        "total_claim_amount",
        "average_claim_amount",
        "total_events",
        "mobile_events"
    ]

    for column in numeric_fill_columns:

        if column in customer_360.columns:

            customer_360[column] = (
                customer_360[column]
                .fillna(0)
            )

    # --------------------------------------------------------
    # CUSTOMER KPIs
    # --------------------------------------------------------

    customer_360["claim_frequency"] = (
        customer_360["total_claims"]
        / customer_360["total_policies"]
        .replace(0, pd.NA)
    ).fillna(0)

    customer_360["loss_ratio_proxy"] = (
        customer_360["total_claim_amount"]
        / customer_360["total_policy_premium"]
        .replace(0, pd.NA)
    ).fillna(0)

    customer_360["mobile_event_share"] = (
        customer_360["mobile_events"]
        / customer_360["total_events"]
        .replace(0, pd.NA)
    ).fillna(0)

    print(
        f"Customer 360 rows: "
        f"{len(customer_360):,}"
    )

    print(
        f"Customer 360 columns: "
        f"{len(customer_360.columns)}"
    )

    print(
        f"Customers with policies: "
        f"{(customer_360['total_policies'] > 0).sum():,}"
    )

    print(
        f"Customers with claims: "
        f"{(customer_360['total_claims'] > 0).sum():,}"
    )

    return customer_360


# ============================================================
# DAILY BUSINESS SUMMARY
# ============================================================

def create_daily_business_summary(
    fact_quotes,
    fact_policies,
    fact_claims,
    fact_events
):

    print_section("CREATE DAILY BUSINESS SUMMARY")

    # Quotes
    quote_daily = (
        fact_quotes
        .groupby(
            fact_quotes["quote_date"].dt.date
        )
        .agg(
            quotes=(
                "quote_id",
                "count"
            ),
            conversions=(
                "is_converted",
                "sum"
            ),
            quoted_premium=(
                "premium_amount",
                "sum"
            )
        )
        .reset_index()
        .rename(
            columns={
                "quote_date": "date"
            }
        )
    )

    quote_daily.columns = [
        "date",
        "quotes",
        "conversions",
        "quoted_premium"
    ]

    # Policies
    policy_daily = (
        fact_policies
        .groupby(
            fact_policies[
                "policy_start_date"
            ].dt.date
        )
        .agg(
            policies=(
                "policy_id",
                "count"
            ),
            written_premium=(
                "premium_amount",
                "sum"
            )
        )
        .reset_index()
    )

    policy_daily.columns = [
        "date",
        "policies",
        "written_premium"
    ]

    # Claims
    claim_daily = (
        fact_claims
        .groupby(
            fact_claims["claim_date"].dt.date
        )
        .agg(
            claims=(
                "claim_id",
                "count"
            ),
            claim_amount=(
                "claim_amount",
                "sum"
            )
        )
        .reset_index()
    )

    claim_daily.columns = [
        "date",
        "claims",
        "claim_amount"
    ]

    # Events
    event_daily = (
        fact_events
        .groupby(
            fact_events[
                "event_timestamp"
            ].dt.date
        )
        .agg(
            events=(
                "event_id",
                "count"
            )
        )
        .reset_index()
    )

    event_daily.columns = [
        "date",
        "events"
    ]

    # Merge
    daily_summary = (
        quote_daily
        .merge(
            policy_daily,
            on="date",
            how="outer"
        )
        .merge(
            claim_daily,
            on="date",
            how="outer"
        )
        .merge(
            event_daily,
            on="date",
            how="outer"
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    metric_columns = [
        "quotes",
        "conversions",
        "quoted_premium",
        "policies",
        "written_premium",
        "claims",
        "claim_amount",
        "events"
    ]

    daily_summary[
        metric_columns
    ] = daily_summary[
        metric_columns
    ].fillna(0)

    daily_summary["conversion_rate"] = (
        daily_summary["conversions"]
        / daily_summary["quotes"]
        .replace(0, pd.NA)
    ).fillna(0)

    print(
        f"Daily summary rows: "
        f"{len(daily_summary):,}"
    )

    if not daily_summary.empty:

        print(
            f"Date range: "
            f"{daily_summary['date'].min()} "
            f"to "
            f"{daily_summary['date'].max()}"
        )

    return daily_summary


# ============================================================
# SAVE TRANSFORMED TABLES
# ============================================================

def save_transformed_tables(tables):

    print_section("SAVE TRANSFORMED TABLES")

    for table_name, df in tables.items():

        output_path = (
            TRANSFORMED_DATA_DIR
            / f"{table_name}.csv"
        )

        df.to_csv(
            output_path,
            index=False
        )

        print(
            f"{table_name:<25} -> "
            f"{len(df):>10,} rows | "
            f"{len(df.columns):>2} columns"
        )


# ============================================================
# TRANSFORMATION VALIDATION
# ============================================================

def validate_transformations(tables):

    print_section("TRANSFORMATION VALIDATION")

    checks = []

    # Customer dimension PK
    customer_duplicates = int(
        tables["dim_customer"][
            "customer_id"
        ].duplicated().sum()
    )

    checks.append({
        "check":
            "dim_customer customer_id uniqueness",
        "failed_records":
            customer_duplicates
    })

    # Quote fact PK
    quote_duplicates = int(
        tables["fact_quotes"][
            "quote_id"
        ].duplicated().sum()
    )

    checks.append({
        "check":
            "fact_quotes quote_id uniqueness",
        "failed_records":
            quote_duplicates
    })

    # Policy fact PK
    policy_duplicates = int(
        tables["fact_policies"][
            "policy_id"
        ].duplicated().sum()
    )

    checks.append({
        "check":
            "fact_policies policy_id uniqueness",
        "failed_records":
            policy_duplicates
    })

    # Claim fact PK
    claim_duplicates = int(
        tables["fact_claims"][
            "claim_id"
        ].duplicated().sum()
    )

    checks.append({
        "check":
            "fact_claims claim_id uniqueness",
        "failed_records":
            claim_duplicates
    })

    # Event fact PK
    event_duplicates = int(
        tables["fact_events"][
            "event_id"
        ].duplicated().sum()
    )

    checks.append({
        "check":
            "fact_events event_id uniqueness",
        "failed_records":
            event_duplicates
    })

    # Customer 360
    customer_360_duplicates = int(
        tables["customer_360"][
            "customer_id"
        ].duplicated().sum()
    )

    checks.append({
        "check":
            "customer_360 customer_id uniqueness",
        "failed_records":
            customer_360_duplicates
    })

    validation_df = pd.DataFrame(
        checks
    )

    validation_df["status"] = (
        validation_df[
            "failed_records"
        ]
        .eq(0)
        .map({
            True: "PASS",
            False: "FAIL"
        })
    )

    for _, row in validation_df.iterrows():

        print(
            f"[{row['status']}] "
            f"{row['check']:<45} "
            f"Failed: "
            f"{row['failed_records']:,}"
        )

    validation_path = (
        TRANSFORMED_DATA_DIR
        / "transformation_validation.csv"
    )

    validation_df.to_csv(
        validation_path,
        index=False
    )

    return validation_df


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print(
        "INSURANCE DATA ENGINEERING PLATFORM "
        "- DATA TRANSFORMATION"
    )
    print("=" * 80)

    datasets = load_clean_data()

    datasets = convert_datetime_columns(
        datasets
    )

    dim_customer = create_customer_dimension(
        datasets["customers"]
    )

    fact_quotes = create_quote_fact(
        datasets["quotes"]
    )

    fact_policies = create_policy_fact(
        datasets["policies"]
    )

    fact_claims = create_claim_fact(
        datasets["claims"],
        fact_policies
    )

    fact_events = create_event_fact(
        datasets["events"]
    )

    customer_360 = create_customer_360(
        dim_customer,
        fact_quotes,
        fact_policies,
        fact_claims,
        fact_events
    )

    daily_summary = (
        create_daily_business_summary(
            fact_quotes,
            fact_policies,
            fact_claims,
            fact_events
        )
    )

    tables = {
        "dim_customer":
            dim_customer,

        "fact_quotes":
            fact_quotes,

        "fact_policies":
            fact_policies,

        "fact_claims":
            fact_claims,

        "fact_events":
            fact_events,

        "customer_360":
            customer_360,

        "daily_business_summary":
            daily_summary
    }

    save_transformed_tables(
        tables
    )

    validation_df = (
        validate_transformations(
            tables
        )
    )

    print_section(
        "FINAL TRANSFORMATION CHECK"
    )

    print(
        f"Transformed tables created: "
        f"{len(tables)}"
    )

    print(
        f"Validation checks passed: "
        f"{(validation_df['status'] == 'PASS').sum()}"
        f"/{len(validation_df)}"
    )

    print(
        f"Customer 360 records: "
        f"{len(customer_360):,}"
    )

    print(
        f"Fact quote records: "
        f"{len(fact_quotes):,}"
    )

    print(
        f"Fact policy records: "
        f"{len(fact_policies):,}"
    )

    print(
        f"Fact claim records: "
        f"{len(fact_claims):,}"
    )

    print(
        f"Fact event records: "
        f"{len(fact_events):,}"
    )

    print("\n" + "=" * 80)
    print(
        "DATA TRANSFORMATION COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()