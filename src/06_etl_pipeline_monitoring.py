from pathlib import Path
from datetime import datetime
import sqlite3
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_FILE = (
    PROJECT_ROOT
    / "database"
    / "insurance_analytics.db"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "monitoring"
)

OUTPUT_DIR.mkdir(
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


def add_check(
    results,
    category,
    check_name,
    actual_value,
    expected_value,
    status
):

    results.append({
        "category": category,
        "check_name": check_name,
        "actual_value": actual_value,
        "expected_value": expected_value,
        "status": status,
        "check_timestamp": datetime.now()
    })

    print(
        f"[{status}] "
        f"{check_name:<50} "
        f"Actual: {actual_value}"
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

def connect_database():

    print_section(
        "DATABASE CONNECTION"
    )

    if not DATABASE_FILE.exists():

        raise FileNotFoundError(
            f"Database not found: "
            f"{DATABASE_FILE}"
        )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    print("Database connection successful.")
    print(DATABASE_FILE)

    return connection


# ============================================================
# TABLE AVAILABILITY
# ============================================================

def validate_database_objects(
    connection,
    results
):

    print_section(
        "DATABASE OBJECT VALIDATION"
    )

    expected_tables = [
        "dim_customer",
        "fact_quotes",
        "fact_policies",
        "fact_claims",
        "fact_events",
        "customer_360",
        "daily_business_summary"
    ]

    expected_views = [
        "vw_quote_conversion_by_channel",
        "vw_product_performance",
        "vw_policy_portfolio",
        "vw_claim_performance",
        "vw_customer_value"
    ]

    database_objects = pd.read_sql_query(
        """
        SELECT
            name,
            type
        FROM sqlite_master
        WHERE type IN ('table', 'view');
        """,
        connection
    )

    for table in expected_tables:

        exists = (
            (
                database_objects["name"]
                == table
            )
            & (
                database_objects["type"]
                == "table"
            )
        ).any()

        add_check(
            results,
            "Database Object",
            f"Table exists: {table}",
            int(exists),
            1,
            "PASS" if exists else "FAIL"
        )

    for view in expected_views:

        exists = (
            (
                database_objects["name"]
                == view
            )
            & (
                database_objects["type"]
                == "view"
            )
        ).any()

        add_check(
            results,
            "Database Object",
            f"View exists: {view}",
            int(exists),
            1,
            "PASS" if exists else "FAIL"
        )


# ============================================================
# ROW COUNT VALIDATION
# ============================================================

def validate_row_counts(
    connection,
    results
):

    print_section(
        "ROW COUNT VALIDATION"
    )

    expected_counts = {
        "dim_customer": 10000,
        "fact_quotes": 50000,
        "fact_policies": 10613,
        "fact_claims": 4000,
        "fact_events": 100000,
        "customer_360": 10000
    }

    for table, expected in expected_counts.items():

        actual = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {table};
            """
        ).fetchone()[0]

        add_check(
            results,
            "Row Count",
            f"{table} row count",
            actual,
            expected,
            "PASS"
            if actual == expected
            else "FAIL"
        )


# ============================================================
# PRIMARY KEY VALIDATION
# ============================================================

def validate_primary_keys(
    connection,
    results
):

    print_section(
        "PRIMARY KEY QUALITY MONITORING"
    )

    primary_keys = {
        "dim_customer":
            "customer_id",

        "fact_quotes":
            "quote_id",

        "fact_policies":
            "policy_id",

        "fact_claims":
            "claim_id",

        "fact_events":
            "event_id",

        "customer_360":
            "customer_id"
    }

    for table, key in primary_keys.items():

        missing = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE {key} IS NULL;
            """
        ).fetchone()[0]

        add_check(
            results,
            "Primary Key",
            f"{table}.{key} missing values",
            missing,
            0,
            "PASS"
            if missing == 0
            else "FAIL"
        )

        duplicates = connection.execute(
            f"""
            SELECT
                COUNT(*)
            FROM (
                SELECT
                    {key},
                    COUNT(*) AS record_count
                FROM {table}
                GROUP BY {key}
                HAVING COUNT(*) > 1
            );
            """
        ).fetchone()[0]

        add_check(
            results,
            "Primary Key",
            f"{table}.{key} duplicate keys",
            duplicates,
            0,
            "PASS"
            if duplicates == 0
            else "FAIL"
        )


# ============================================================
# REFERENTIAL INTEGRITY
# ============================================================

def validate_referential_integrity(
    connection,
    results
):

    print_section(
        "REFERENTIAL INTEGRITY MONITORING"
    )

    checks = [
        (
            "fact_quotes -> dim_customer",
            """
            SELECT COUNT(*)
            FROM fact_quotes q
            LEFT JOIN dim_customer c
                ON q.customer_id = c.customer_id
            WHERE c.customer_id IS NULL;
            """
        ),

        (
            "fact_policies -> dim_customer",
            """
            SELECT COUNT(*)
            FROM fact_policies p
            LEFT JOIN dim_customer c
                ON p.customer_id = c.customer_id
            WHERE c.customer_id IS NULL;
            """
        ),

        (
            "fact_policies -> fact_quotes",
            """
            SELECT COUNT(*)
            FROM fact_policies p
            LEFT JOIN fact_quotes q
                ON p.quote_id = q.quote_id
            WHERE q.quote_id IS NULL;
            """
        ),

        (
            "fact_claims -> fact_policies",
            """
            SELECT COUNT(*)
            FROM fact_claims c
            LEFT JOIN fact_policies p
                ON c.policy_id = p.policy_id
            WHERE p.policy_id IS NULL;
            """
        ),

        (
            "fact_events -> dim_customer",
            """
            SELECT COUNT(*)
            FROM fact_events e
            LEFT JOIN dim_customer c
                ON e.customer_id = c.customer_id
            WHERE c.customer_id IS NULL;
            """
        )
    ]

    for check_name, query in checks:

        orphan_records = (
            connection
            .execute(query)
            .fetchone()[0]
        )

        add_check(
            results,
            "Referential Integrity",
            check_name,
            orphan_records,
            0,
            "PASS"
            if orphan_records == 0
            else "FAIL"
        )


# ============================================================
# BUSINESS RULE MONITORING
# ============================================================

def validate_business_rules(
    connection,
    results
):

    print_section(
        "BUSINESS RULE MONITORING"
    )

    # Quote premium
    invalid_quote_premium = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_quotes
            WHERE premium_amount IS NULL
               OR premium_amount <= 0;
            """
        ).fetchone()[0]
    )

    add_check(
        results,
        "Business Rule",
        "Invalid quote premium",
        invalid_quote_premium,
        0,
        "PASS"
        if invalid_quote_premium == 0
        else "FAIL"
    )

    # Policy premium
    invalid_policy_premium = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_policies
            WHERE premium_amount IS NULL
               OR premium_amount <= 0;
            """
        ).fetchone()[0]
    )

    add_check(
        results,
        "Business Rule",
        "Invalid policy premium",
        invalid_policy_premium,
        0,
        "PASS"
        if invalid_policy_premium == 0
        else "FAIL"
    )

    # Claim amount
    invalid_claim_amount = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_claims
            WHERE claim_amount IS NULL
               OR claim_amount <= 0;
            """
        ).fetchone()[0]
    )

    add_check(
        results,
        "Business Rule",
        "Invalid claim amount",
        invalid_claim_amount,
        0,
        "PASS"
        if invalid_claim_amount == 0
        else "FAIL"
    )

    # Conversion flag
    invalid_conversion = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_quotes
            WHERE is_converted NOT IN (0, 1)
               OR is_converted IS NULL;
            """
        ).fetchone()[0]
    )

    add_check(
        results,
        "Business Rule",
        "Invalid quote conversion flag",
        invalid_conversion,
        0,
        "PASS"
        if invalid_conversion == 0
        else "FAIL"
    )


# ============================================================
# KPI MONITORING
# ============================================================

def calculate_pipeline_kpis(
    connection
):

    print_section(
        "PIPELINE KPI MONITORING"
    )

    total_customers = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM dim_customer;
            """
        ).fetchone()[0]
    )

    total_quotes = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_quotes;
            """
        ).fetchone()[0]
    )

    converted_quotes = (
        connection.execute(
            """
            SELECT SUM(is_converted)
            FROM fact_quotes;
            """
        ).fetchone()[0]
    )

    total_policies = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_policies;
            """
        ).fetchone()[0]
    )

    total_claims = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_claims;
            """
        ).fetchone()[0]
    )

    total_events = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_events;
            """
        ).fetchone()[0]
    )

    written_premium = (
        connection.execute(
            """
            SELECT SUM(premium_amount)
            FROM fact_policies;
            """
        ).fetchone()[0]
    )

    total_claim_amount = (
        connection.execute(
            """
            SELECT SUM(claim_amount)
            FROM fact_claims;
            """
        ).fetchone()[0]
    )

    conversion_rate = (
        converted_quotes
        / total_quotes
        if total_quotes > 0
        else 0
    )

    loss_ratio_proxy = (
        total_claim_amount
        / written_premium
        if written_premium > 0
        else 0
    )

    kpis = {
        "total_customers":
            total_customers,

        "total_quotes":
            total_quotes,

        "converted_quotes":
            converted_quotes,

        "conversion_rate":
            conversion_rate,

        "total_policies":
            total_policies,

        "total_claims":
            total_claims,

        "total_events":
            total_events,

        "written_premium":
            written_premium,

        "total_claim_amount":
            total_claim_amount,

        "loss_ratio_proxy":
            loss_ratio_proxy
    }

    print(
        f"Customers:          "
        f"{total_customers:,}"
    )

    print(
        f"Quotes:             "
        f"{total_quotes:,}"
    )

    print(
        f"Converted Quotes:   "
        f"{converted_quotes:,}"
    )

    print(
        f"Conversion Rate:    "
        f"{conversion_rate * 100:.2f}%"
    )

    print(
        f"Policies:           "
        f"{total_policies:,}"
    )

    print(
        f"Claims:             "
        f"{total_claims:,}"
    )

    print(
        f"Events:             "
        f"{total_events:,}"
    )

    print(
        f"Written Premium:    "
        f"{written_premium:,.2f}"
    )

    print(
        f"Claim Amount:       "
        f"{total_claim_amount:,.2f}"
    )

    print(
        f"Loss Ratio Proxy:   "
        f"{loss_ratio_proxy * 100:.2f}%"
    )

    return kpis


# ============================================================
# SAVE MONITORING OUTPUTS
# ============================================================

def save_outputs(
    results,
    kpis
):

    print_section(
        "SAVE MONITORING OUTPUTS"
    )

    results_df = pd.DataFrame(
        results
    )

    checks_path = (
        OUTPUT_DIR
        / "pipeline_quality_checks.csv"
    )

    results_df.to_csv(
        checks_path,
        index=False
    )

    kpi_df = pd.DataFrame(
        [
            {
                **kpis,
                "monitoring_timestamp":
                    datetime.now()
            }
        ]
    )

    kpi_path = (
        OUTPUT_DIR
        / "pipeline_kpis.csv"
    )

    kpi_df.to_csv(
        kpi_path,
        index=False
    )

    summary = (
        results_df
        .groupby(
            [
                "category",
                "status"
            ]
        )
        .size()
        .reset_index(
            name="check_count"
        )
    )

    summary_path = (
        OUTPUT_DIR
        / "pipeline_check_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False
    )

    print(
        f"Quality checks:\n"
        f"{checks_path}"
    )

    print(
        f"\nPipeline KPIs:\n"
        f"{kpi_path}"
    )

    print(
        f"\nCheck summary:\n"
        f"{summary_path}"
    )

    return results_df


# ============================================================
# FINAL PIPELINE STATUS
# ============================================================

def evaluate_pipeline_status(
    results_df
):

    print_section(
        "FINAL PIPELINE STATUS"
    )

    total_checks = len(
        results_df
    )

    passed_checks = (
        results_df["status"]
        .eq("PASS")
        .sum()
    )

    failed_checks = (
        results_df["status"]
        .eq("FAIL")
        .sum()
    )

    if failed_checks == 0:

        pipeline_status = (
            "HEALTHY"
        )

    else:

        pipeline_status = (
            "ATTENTION REQUIRED"
        )

    print(
        f"Total checks:  "
        f"{total_checks}"
    )

    print(
        f"Passed checks: "
        f"{passed_checks}"
    )

    print(
        f"Failed checks: "
        f"{failed_checks}"
    )

    print(
        f"Pipeline status: "
        f"{pipeline_status}"
    )

    return pipeline_status


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)

    print(
        "INSURANCE DATA ENGINEERING PLATFORM "
        "- ETL PIPELINE MONITORING"
    )

    print("=" * 80)

    results = []

    connection = (
        connect_database()
    )

    try:

        validate_database_objects(
            connection,
            results
        )

        validate_row_counts(
            connection,
            results
        )

        validate_primary_keys(
            connection,
            results
        )

        validate_referential_integrity(
            connection,
            results
        )

        validate_business_rules(
            connection,
            results
        )

        kpis = (
            calculate_pipeline_kpis(
                connection
            )
        )

        results_df = (
            save_outputs(
                results,
                kpis
            )
        )

        pipeline_status = (
            evaluate_pipeline_status(
                results_df
            )
        )

    finally:

        connection.close()

    print("\n" + "=" * 80)

    print(
        "ETL PIPELINE MONITORING COMPLETED"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()