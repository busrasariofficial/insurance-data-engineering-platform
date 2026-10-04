from pathlib import Path
from datetime import datetime
import sqlite3
import sys

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
    / "tests"
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


def add_test(
    results,
    category,
    test_name,
    expected,
    actual,
    status
):

    results.append({
        "category": category,
        "test_name": test_name,
        "expected": expected,
        "actual": actual,
        "status": status,
        "test_timestamp": datetime.now()
    })

    print(
        f"[{status}] "
        f"{test_name:<55} "
        f"Actual: {actual}"
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

    print(
        "Database connection successful."
    )

    print(
        DATABASE_FILE
    )

    return connection


# ============================================================
# DATABASE OBJECT TESTS
# ============================================================

def test_database_objects(
    connection,
    results
):

    print_section(
        "DATABASE OBJECT TESTS"
    )

    required_tables = [
        "dim_customer",
        "fact_quotes",
        "fact_policies",
        "fact_claims",
        "fact_events",
        "customer_360",
        "daily_business_summary",
        "etl_watermarks",
        "incremental_load_audit"
    ]

    objects = pd.read_sql_query(
        """
        SELECT
            name,
            type

        FROM sqlite_master

        WHERE type IN (
            'table',
            'view'
        );
        """,
        connection
    )

    for table in required_tables:

        exists = (
            (
                objects["name"]
                == table
            )
            & (
                objects["type"]
                == "table"
            )
        ).any()

        add_test(
            results,
            "Database Objects",
            f"Required table exists: {table}",
            1,
            int(exists),
            "PASS"
            if exists
            else "FAIL"
        )


# ============================================================
# SCHEMA TESTS
# ============================================================

def test_table_schemas(
    connection,
    results
):

    print_section(
        "SCHEMA TESTS"
    )

    expected_columns = {

        "dim_customer": [
            "customer_id",
            "age",
            "age_group",
            "gender",
            "city",
            "registration_date",
            "registration_year",
            "registration_month",
            "registration_month_name"
        ],

        "fact_quotes": [
            "quote_id",
            "customer_id",
            "quote_date",
            "product_type",
            "premium_amount",
            "channel",
            "is_converted"
        ],

        "fact_policies": [
            "policy_id",
            "customer_id",
            "quote_id",
            "policy_start_date",
            "policy_end_date",
            "product_type",
            "premium_amount",
            "policy_status"
        ],

        "fact_claims": [
            "claim_id",
            "policy_id",
            "customer_id",
            "claim_date",
            "claim_amount",
            "claim_status"
        ],

        "fact_events": [
            "event_id",
            "customer_id",
            "event_type",
            "device_type",
            "event_timestamp",
            "event_date",
            "event_year",
            "event_month",
            "event_day",
            "event_hour",
            "event_day_of_week",
            "is_mobile"
        ]
    }

    for table, columns in expected_columns.items():

        schema = pd.read_sql_query(
            f"""
            PRAGMA table_info({table});
            """,
            connection
        )

        actual_columns = set(
            schema["name"]
        )

        for column in columns:

            exists = (
                column
                in actual_columns
            )

            add_test(
                results,
                "Schema",
                f"{table}.{column} exists",
                1,
                int(exists),
                "PASS"
                if exists
                else "FAIL"
            )


# ============================================================
# ROW COUNT TESTS
# ============================================================

def test_row_counts(
    connection,
    results
):

    print_section(
        "ROW COUNT TESTS"
    )

    minimum_counts = {

        "dim_customer":
            10000,

        "fact_quotes":
            50000,

        "fact_policies":
            10613,

        "fact_claims":
            4000,

        "fact_events":
            100000,

        "customer_360":
            10000
    }

    for table, minimum in minimum_counts.items():

        actual = (
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM {table};
                """
            ).fetchone()[0]
        )

        status = (
            "PASS"
            if actual >= minimum
            else "FAIL"
        )

        add_test(
            results,
            "Row Count",
            f"{table} minimum row count",
            f">= {minimum}",
            actual,
            status
        )


# ============================================================
# PRIMARY KEY TESTS
# ============================================================

def test_primary_keys(
    connection,
    results
):

    print_section(
        "PRIMARY KEY TESTS"
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

        # ----------------------------------------------------
        # NULL TEST
        # ----------------------------------------------------

        null_count = (
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {key} IS NULL;
                """
            ).fetchone()[0]
        )

        add_test(
            results,
            "Primary Key",
            f"{table}.{key} contains no NULLs",
            0,
            null_count,
            "PASS"
            if null_count == 0
            else "FAIL"
        )

        # ----------------------------------------------------
        # DUPLICATE TEST
        # ----------------------------------------------------

        duplicate_count = (
            connection.execute(
                f"""
                SELECT COUNT(*)

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
        )

        add_test(
            results,
            "Primary Key",
            f"{table}.{key} contains no duplicates",
            0,
            duplicate_count,
            "PASS"
            if duplicate_count == 0
            else "FAIL"
        )


# ============================================================
# REFERENTIAL INTEGRITY TESTS
# ============================================================

def test_referential_integrity(
    connection,
    results
):

    print_section(
        "REFERENTIAL INTEGRITY TESTS"
    )

    tests = [

        (
            "fact_quotes.customer_id -> dim_customer",
            """
            SELECT COUNT(*)

            FROM fact_quotes q

            LEFT JOIN dim_customer c
                ON q.customer_id = c.customer_id

            WHERE c.customer_id IS NULL;
            """
        ),

        (
            "fact_policies.customer_id -> dim_customer",
            """
            SELECT COUNT(*)

            FROM fact_policies p

            LEFT JOIN dim_customer c
                ON p.customer_id = c.customer_id

            WHERE c.customer_id IS NULL;
            """
        ),

        (
            "fact_policies.quote_id -> fact_quotes",
            """
            SELECT COUNT(*)

            FROM fact_policies p

            LEFT JOIN fact_quotes q
                ON p.quote_id = q.quote_id

            WHERE q.quote_id IS NULL;
            """
        ),

        (
            "fact_claims.policy_id -> fact_policies",
            """
            SELECT COUNT(*)

            FROM fact_claims c

            LEFT JOIN fact_policies p
                ON c.policy_id = p.policy_id

            WHERE p.policy_id IS NULL;
            """
        ),

        (
            "fact_claims.customer_id -> dim_customer",
            """
            SELECT COUNT(*)

            FROM fact_claims cl

            LEFT JOIN dim_customer c
                ON cl.customer_id = c.customer_id

            WHERE c.customer_id IS NULL;
            """
        ),

        (
            "fact_events.customer_id -> dim_customer",
            """
            SELECT COUNT(*)

            FROM fact_events e

            LEFT JOIN dim_customer c
                ON e.customer_id = c.customer_id

            WHERE c.customer_id IS NULL;
            """
        )
    ]

    for test_name, query in tests:

        orphan_count = (
            connection.execute(
                query
            ).fetchone()[0]
        )

        add_test(
            results,
            "Referential Integrity",
            test_name,
            0,
            orphan_count,
            "PASS"
            if orphan_count == 0
            else "FAIL"
        )


# ============================================================
# BUSINESS RULE TESTS
# ============================================================

def test_business_rules(
    connection,
    results
):

    print_section(
        "BUSINESS RULE TESTS"
    )

    business_tests = [

        (
            "Customer age between 18 and 100",
            """
            SELECT COUNT(*)
            FROM dim_customer

            WHERE age < 18
               OR age > 100
               OR age IS NULL;
            """
        ),

        (
            "Quote premium must be positive",
            """
            SELECT COUNT(*)
            FROM fact_quotes

            WHERE premium_amount <= 0
               OR premium_amount IS NULL;
            """
        ),

        (
            "Policy premium must be positive",
            """
            SELECT COUNT(*)
            FROM fact_policies

            WHERE premium_amount <= 0
               OR premium_amount IS NULL;
            """
        ),

        (
            "Claim amount must be positive",
            """
            SELECT COUNT(*)
            FROM fact_claims

            WHERE claim_amount <= 0
               OR claim_amount IS NULL;
            """
        ),

        (
            "Quote conversion flag must be 0 or 1",
            """
            SELECT COUNT(*)
            FROM fact_quotes

            WHERE is_converted NOT IN (0, 1)
               OR is_converted IS NULL;
            """
        ),

        (
            "Policy end date must be after start date",
            """
            SELECT COUNT(*)
            FROM fact_policies

            WHERE date(policy_end_date)
                  <= date(policy_start_date);
            """
        ),

        (
            "Event mobile flag must be 0 or 1",
            """
            SELECT COUNT(*)
            FROM fact_events

            WHERE is_mobile NOT IN (0, 1)
               OR is_mobile IS NULL;
            """
        )
    ]

    for test_name, query in business_tests:

        invalid_records = (
            connection.execute(
                query
            ).fetchone()[0]
        )

        add_test(
            results,
            "Business Rule",
            test_name,
            0,
            invalid_records,
            "PASS"
            if invalid_records == 0
            else "FAIL"
        )


# ============================================================
# INCREMENTAL ETL TESTS
# ============================================================

def test_incremental_etl(
    connection,
    results
):

    print_section(
        "INCREMENTAL ETL TESTS"
    )

    # --------------------------------------------------------
    # WATERMARK EXISTS
    # --------------------------------------------------------

    watermark_result = (
        connection.execute(
            """
            SELECT last_watermark

            FROM etl_watermarks

            WHERE pipeline_name =
                'insurance_event_incremental_load';
            """
        ).fetchone()
    )

    watermark_exists = (
        watermark_result is not None
        and watermark_result[0] is not None
    )

    add_test(
        results,
        "Incremental ETL",
        "Incremental watermark exists",
        1,
        int(watermark_exists),
        "PASS"
        if watermark_exists
        else "FAIL"
    )

    # --------------------------------------------------------
    # AUDIT RECORD EXISTS
    # --------------------------------------------------------

    audit_count = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM incremental_load_audit;
            """
        ).fetchone()[0]
    )

    add_test(
        results,
        "Incremental ETL",
        "Incremental load audit record exists",
        ">= 1",
        audit_count,
        "PASS"
        if audit_count >= 1
        else "FAIL"
    )

    # --------------------------------------------------------
    # LATEST LOAD SUCCESSFUL
    # --------------------------------------------------------

    latest_status = (
        connection.execute(
            """
            SELECT load_status

            FROM incremental_load_audit

            ORDER BY audit_id DESC

            LIMIT 1;
            """
        ).fetchone()
    )

    if latest_status is None:

        status_value = "MISSING"

    else:

        status_value = (
            latest_status[0]
        )

    add_test(
        results,
        "Incremental ETL",
        "Latest incremental load status",
        "SUCCESS",
        status_value,
        "PASS"
        if status_value == "SUCCESS"
        else "FAIL"
    )

    # --------------------------------------------------------
    # WATERMARK CONSISTENCY
    # --------------------------------------------------------

    if watermark_exists:

        watermark = pd.to_datetime(
            watermark_result[0]
        )

        max_event_timestamp = (
            connection.execute(
                """
                SELECT MAX(event_timestamp)
                FROM fact_events;
                """
            ).fetchone()[0]
        )

        max_event_timestamp = (
            pd.to_datetime(
                max_event_timestamp
            )
        )

        consistent = (
            watermark
            == max_event_timestamp
        )

        add_test(
            results,
            "Incremental ETL",
            "Watermark equals max event timestamp",
            str(max_event_timestamp),
            str(watermark),
            "PASS"
            if consistent
            else "FAIL"
        )


# ============================================================
# ANALYTICAL VIEW TESTS
# ============================================================

def test_analytical_views(
    connection,
    results
):

    print_section(
        "ANALYTICAL VIEW TESTS"
    )

    views = [
        "vw_quote_conversion_by_channel",
        "vw_product_performance",
        "vw_policy_portfolio",
        "vw_claim_performance",
        "vw_customer_value"
    ]

    for view in views:

        try:

            row_count = (
                connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {view};
                    """
                ).fetchone()[0]
            )

            status = (
                "PASS"
                if row_count > 0
                else "FAIL"
            )

            add_test(
                results,
                "Analytical Views",
                f"{view} returns records",
                "> 0",
                row_count,
                status
            )

        except sqlite3.Error:

            add_test(
                results,
                "Analytical Views",
                f"{view} returns records",
                "> 0",
                "ERROR",
                "FAIL"
            )


# ============================================================
# KPI CONSISTENCY TESTS
# ============================================================

def test_kpi_consistency(
    connection,
    results
):

    print_section(
        "KPI CONSISTENCY TESTS"
    )

    # --------------------------------------------------------
    # CONVERTED QUOTES VS POLICIES
    # --------------------------------------------------------

    converted_quotes = (
        connection.execute(
            """
            SELECT COUNT(*)

            FROM fact_quotes

            WHERE is_converted = 1;
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

    conversion_policy_match = (
        converted_quotes
        == total_policies
    )

    add_test(
        results,
        "KPI Consistency",
        "Converted quotes equal policy count",
        total_policies,
        converted_quotes,
        "PASS"
        if conversion_policy_match
        else "FAIL"
    )

    # --------------------------------------------------------
    # CUSTOMER 360 COUNT
    # --------------------------------------------------------

    dim_customer_count = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM dim_customer;
            """
        ).fetchone()[0]
    )

    customer_360_count = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM customer_360;
            """
        ).fetchone()[0]
    )

    add_test(
        results,
        "KPI Consistency",
        "Customer 360 covers all customers",
        dim_customer_count,
        customer_360_count,
        "PASS"
        if (
            dim_customer_count
            == customer_360_count
        )
        else "FAIL"
    )

    # --------------------------------------------------------
    # CONVERSION RATE RANGE
    # --------------------------------------------------------

    conversion_rate = (
        connection.execute(
            """
            SELECT
                1.0 * SUM(is_converted)
                / COUNT(*)

            FROM fact_quotes;
            """
        ).fetchone()[0]
    )

    valid_conversion_rate = (
        0 <= conversion_rate <= 1
    )

    add_test(
        results,
        "KPI Consistency",
        "Conversion rate between 0 and 1",
        "0 <= rate <= 1",
        round(
            conversion_rate,
            4
        ),
        "PASS"
        if valid_conversion_rate
        else "FAIL"
    )


# ============================================================
# SAVE TEST RESULTS
# ============================================================

def save_test_results(
    results
):

    print_section(
        "SAVE TEST RESULTS"
    )

    results_df = pd.DataFrame(
        results
    )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    detailed_file = (
        OUTPUT_DIR
        / (
            f"pipeline_test_results_"
            f"{timestamp}.csv"
        )
    )

    results_df.to_csv(
        detailed_file,
        index=False
    )

    summary_df = (
        results_df
        .groupby(
            [
                "category",
                "status"
            ]
        )
        .size()
        .reset_index(
            name="test_count"
        )
    )

    summary_file = (
        OUTPUT_DIR
        / (
            f"pipeline_test_summary_"
            f"{timestamp}.csv"
        )
    )

    summary_df.to_csv(
        summary_file,
        index=False
    )

    print(
        "Detailed test results:"
    )

    print(
        detailed_file
    )

    print(
        "\nTest summary:"
    )

    print(
        summary_file
    )

    return results_df


# ============================================================
# FINAL TEST REPORT
# ============================================================

def print_final_report(
    results_df
):

    print_section(
        "AUTOMATED TEST REPORT"
    )

    total_tests = len(
        results_df
    )

    passed_tests = int(
        results_df[
            "status"
        ]
        .eq("PASS")
        .sum()
    )

    failed_tests = int(
        results_df[
            "status"
        ]
        .eq("FAIL")
        .sum()
    )

    pass_rate = (
        passed_tests
        / total_tests
        * 100
        if total_tests > 0
        else 0
    )

    print(
        f"Total tests:  "
        f"{total_tests}"
    )

    print(
        f"Passed tests: "
        f"{passed_tests}"
    )

    print(
        f"Failed tests: "
        f"{failed_tests}"
    )

    print(
        f"Pass rate:    "
        f"{pass_rate:.2f}%"
    )

    if failed_tests == 0:

        overall_status = (
            "ALL TESTS PASSED"
        )

    else:

        overall_status = (
            "TEST FAILURES DETECTED"
        )

    print(
        f"Overall status: "
        f"{overall_status}"
    )

    return failed_tests


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)

    print(
        "INSURANCE DATA ENGINEERING PLATFORM "
        "- AUTOMATED PIPELINE TESTS"
    )

    print("=" * 80)

    results = []

    connection = (
        connect_database()
    )

    try:

        test_database_objects(
            connection,
            results
        )

        test_table_schemas(
            connection,
            results
        )

        test_row_counts(
            connection,
            results
        )

        test_primary_keys(
            connection,
            results
        )

        test_referential_integrity(
            connection,
            results
        )

        test_business_rules(
            connection,
            results
        )

        test_incremental_etl(
            connection,
            results
        )

        test_analytical_views(
            connection,
            results
        )

        test_kpi_consistency(
            connection,
            results
        )

    finally:

        connection.close()

    results_df = (
        save_test_results(
            results
        )
    )

    failed_tests = (
        print_final_report(
            results_df
        )
    )

    print("\n" + "=" * 80)

    print(
        "AUTOMATED PIPELINE TESTING COMPLETED"
    )

    print("=" * 80)

    # Important for GitHub Actions:
    # any failed test returns a non-zero exit code.
    if failed_tests > 0:

        sys.exit(1)


if __name__ == "__main__":
    main()