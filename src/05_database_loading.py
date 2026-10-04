from pathlib import Path
import sqlite3
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSFORMED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "transformed"
)

DATABASE_DIR = (
    PROJECT_ROOT
    / "database"
)

DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

DATABASE_FILE = (
    DATABASE_DIR
    / "insurance_analytics.db"
)


# ============================================================
# HELPERS
# ============================================================

def print_section(title):

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# ============================================================
# LOAD TRANSFORMED DATA
# ============================================================

def load_transformed_data():

    print_section(
        "LOAD TRANSFORMED DATA"
    )

    table_files = {

        "dim_customer":
            "dim_customer.csv",

        "fact_quotes":
            "fact_quotes.csv",

        "fact_policies":
            "fact_policies.csv",

        "fact_claims":
            "fact_claims.csv",

        "fact_events":
            "fact_events.csv",

        "customer_360":
            "customer_360.csv",

        "daily_business_summary":
            "daily_business_summary.csv"
    }

    datasets = {}

    for table_name, filename in table_files.items():

        file_path = (
            TRANSFORMED_DATA_DIR
            / filename
        )

        if not file_path.exists():

            raise FileNotFoundError(
                f"Transformed file not found: "
                f"{file_path}"
            )

        df = pd.read_csv(
            file_path
        )

        datasets[table_name] = df

        print(
            f"{table_name:<25} "
            f"{len(df):>10,} rows | "
            f"{len(df.columns):>2} columns"
        )

    return datasets


# ============================================================
# CREATE DATABASE CONNECTION
# ============================================================

def create_connection():

    print_section(
        "CREATE SQLITE DATABASE"
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.execute(
        "PRAGMA foreign_keys = ON;"
    )

    print(
        f"Database path:\n"
        f"{DATABASE_FILE}"
    )

    return connection


# ============================================================
# LOAD TABLES
# ============================================================

def load_tables_to_database(
    connection,
    datasets
):

    print_section(
        "LOAD TABLES TO DATABASE"
    )

    for table_name, df in datasets.items():

        df.to_sql(
            table_name,
            connection,
            if_exists="replace",
            index=False,
            chunksize=5000
        )

        print(
            f"[LOADED] "
            f"{table_name:<25} "
            f"{len(df):>10,} rows"
        )

    connection.commit()


# ============================================================
# CREATE INDEXES
# ============================================================

def create_indexes(connection):

    print_section(
        "CREATE DATABASE INDEXES"
    )

    index_statements = {

        "idx_customer_id":
        """
        CREATE INDEX IF NOT EXISTS
        idx_customer_id
        ON dim_customer(customer_id);
        """,

        "idx_quotes_customer":
        """
        CREATE INDEX IF NOT EXISTS
        idx_quotes_customer
        ON fact_quotes(customer_id);
        """,

        "idx_quotes_date":
        """
        CREATE INDEX IF NOT EXISTS
        idx_quotes_date
        ON fact_quotes(quote_date);
        """,

        "idx_quotes_product":
        """
        CREATE INDEX IF NOT EXISTS
        idx_quotes_product
        ON fact_quotes(product_type);
        """,

        "idx_policies_customer":
        """
        CREATE INDEX IF NOT EXISTS
        idx_policies_customer
        ON fact_policies(customer_id);
        """,

        "idx_policies_quote":
        """
        CREATE INDEX IF NOT EXISTS
        idx_policies_quote
        ON fact_policies(quote_id);
        """,

        "idx_policies_product":
        """
        CREATE INDEX IF NOT EXISTS
        idx_policies_product
        ON fact_policies(product_type);
        """,

        "idx_claims_customer":
        """
        CREATE INDEX IF NOT EXISTS
        idx_claims_customer
        ON fact_claims(customer_id);
        """,

        "idx_claims_policy":
        """
        CREATE INDEX IF NOT EXISTS
        idx_claims_policy
        ON fact_claims(policy_id);
        """,

        "idx_events_customer":
        """
        CREATE INDEX IF NOT EXISTS
        idx_events_customer
        ON fact_events(customer_id);
        """,

        "idx_events_timestamp":
        """
        CREATE INDEX IF NOT EXISTS
        idx_events_timestamp
        ON fact_events(event_timestamp);
        """,

        "idx_customer360_id":
        """
        CREATE INDEX IF NOT EXISTS
        idx_customer360_id
        ON customer_360(customer_id);
        """
    }

    cursor = connection.cursor()

    for index_name, sql in index_statements.items():

        cursor.execute(sql)

        print(
            f"[CREATED] {index_name}"
        )

    connection.commit()


# ============================================================
# CREATE ANALYTICAL VIEWS
# ============================================================

def create_views(connection):

    print_section(
        "CREATE ANALYTICAL SQL VIEWS"
    )

    cursor = connection.cursor()

    views = {

        "vw_quote_conversion_by_channel":
        """
        CREATE VIEW
        vw_quote_conversion_by_channel
        AS

        SELECT
            channel,
            COUNT(*) AS total_quotes,
            SUM(is_converted) AS converted_quotes,

            ROUND(
                100.0 * SUM(is_converted)
                / COUNT(*),
                2
            ) AS conversion_rate_pct,

            ROUND(
                AVG(premium_amount),
                2
            ) AS average_premium

        FROM fact_quotes

        GROUP BY channel;
        """,

        "vw_product_performance":
        """
        CREATE VIEW
        vw_product_performance
        AS

        SELECT
            product_type,

            COUNT(*) AS total_quotes,

            SUM(is_converted)
                AS converted_quotes,

            ROUND(
                100.0 * SUM(is_converted)
                / COUNT(*),
                2
            ) AS conversion_rate_pct,

            ROUND(
                AVG(premium_amount),
                2
            ) AS average_quoted_premium,

            ROUND(
                SUM(premium_amount),
                2
            ) AS total_quoted_premium

        FROM fact_quotes

        GROUP BY product_type;
        """,

        "vw_policy_portfolio":
        """
        CREATE VIEW
        vw_policy_portfolio
        AS

        SELECT
            product_type,

            COUNT(*) AS total_policies,

            SUM(is_active)
                AS active_policies,

            ROUND(
                SUM(premium_amount),
                2
            ) AS written_premium,

            ROUND(
                AVG(premium_amount),
                2
            ) AS average_policy_premium

        FROM fact_policies

        GROUP BY product_type;
        """,

        "vw_claim_performance":
        """
        CREATE VIEW
        vw_claim_performance
        AS

        SELECT
            claim_status,

            COUNT(*) AS total_claims,

            ROUND(
                SUM(claim_amount),
                2
            ) AS total_claim_amount,

            ROUND(
                AVG(claim_amount),
                2
            ) AS average_claim_amount

        FROM fact_claims

        GROUP BY claim_status;
        """,

        "vw_customer_value":
        """
        CREATE VIEW
        vw_customer_value
        AS

        SELECT
            customer_id,
            age,
            age_group,
            gender,
            city,

            total_quotes,
            converted_quotes,
            customer_conversion_rate,

            total_policies,
            active_policies,
            total_policy_premium,

            total_claims,
            total_claim_amount,

            loss_ratio_proxy,
            total_events,
            mobile_event_share

        FROM customer_360;
        """
    }

    for view_name, sql in views.items():

        cursor.execute(
            f"DROP VIEW IF EXISTS {view_name};"
        )

        cursor.execute(sql)

        print(
            f"[CREATED] {view_name}"
        )

    connection.commit()


# ============================================================
# DATABASE VALIDATION
# ============================================================

def validate_database(
    connection,
    datasets
):

    print_section(
        "DATABASE VALIDATION"
    )

    validation_results = []

    for table_name, source_df in datasets.items():

        query = (
            f"SELECT COUNT(*) "
            f"FROM {table_name};"
        )

        database_count = (
            connection
            .execute(query)
            .fetchone()[0]
        )

        source_count = len(
            source_df
        )

        status = (
            "PASS"
            if database_count == source_count
            else "FAIL"
        )

        print(
            f"[{status}] "
            f"{table_name:<25} "
            f"Source: {source_count:>10,} | "
            f"Database: {database_count:>10,}"
        )

        validation_results.append({
            "table_name":
                table_name,

            "source_rows":
                source_count,

            "database_rows":
                database_count,

            "status":
                status
        })

    return pd.DataFrame(
        validation_results
    )


# ============================================================
# TEST BUSINESS QUERIES
# ============================================================

def run_business_queries(connection):

    print_section(
        "BUSINESS QUERY TESTS"
    )

    # --------------------------------------------------------
    # QUERY 1
    # --------------------------------------------------------

    print(
        "\n1. QUOTE CONVERSION BY CHANNEL"
    )

    query_1 = """
    SELECT *
    FROM vw_quote_conversion_by_channel
    ORDER BY conversion_rate_pct DESC;
    """

    result_1 = pd.read_sql_query(
        query_1,
        connection
    )

    print(
        result_1.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # QUERY 2
    # --------------------------------------------------------

    print(
        "\n2. PRODUCT PERFORMANCE"
    )

    query_2 = """
    SELECT *
    FROM vw_product_performance
    ORDER BY conversion_rate_pct DESC;
    """

    result_2 = pd.read_sql_query(
        query_2,
        connection
    )

    print(
        result_2.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # QUERY 3
    # --------------------------------------------------------

    print(
        "\n3. POLICY PORTFOLIO"
    )

    query_3 = """
    SELECT *
    FROM vw_policy_portfolio
    ORDER BY written_premium DESC;
    """

    result_3 = pd.read_sql_query(
        query_3,
        connection
    )

    print(
        result_3.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # QUERY 4
    # --------------------------------------------------------

    print(
        "\n4. CLAIM PERFORMANCE"
    )

    query_4 = """
    SELECT *
    FROM vw_claim_performance
    ORDER BY total_claim_amount DESC;
    """

    result_4 = pd.read_sql_query(
        query_4,
        connection
    )

    print(
        result_4.to_string(
            index=False
        )
    )


# ============================================================
# DATABASE OBJECT SUMMARY
# ============================================================

def database_summary(connection):

    print_section(
        "DATABASE OBJECT SUMMARY"
    )

    tables_query = """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name;
    """

    views_query = """
    SELECT name
    FROM sqlite_master
    WHERE type = 'view'
    ORDER BY name;
    """

    indexes_query = """
    SELECT name
    FROM sqlite_master
    WHERE type = 'index'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name;
    """

    tables = pd.read_sql_query(
        tables_query,
        connection
    )

    views = pd.read_sql_query(
        views_query,
        connection
    )

    indexes = pd.read_sql_query(
        indexes_query,
        connection
    )

    print(
        f"Tables:  {len(tables)}"
    )

    print(
        f"Views:   {len(views)}"
    )

    print(
        f"Indexes: {len(indexes)}"
    )

    print("\nTables:")

    for name in tables["name"]:
        print(f"- {name}")

    print("\nViews:")

    for name in views["name"]:
        print(f"- {name}")


# ============================================================
# SAVE VALIDATION REPORT
# ============================================================

def save_validation_report(
    validation_df
):

    output_path = (
        TRANSFORMED_DATA_DIR
        / "database_validation.csv"
    )

    validation_df.to_csv(
        output_path,
        index=False
    )

    print("\nDatabase validation saved to:")
    print(output_path)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)

    print(
        "INSURANCE DATA ENGINEERING PLATFORM "
        "- DATABASE LOADING"
    )

    print("=" * 80)

    datasets = (
        load_transformed_data()
    )

    connection = (
        create_connection()
    )

    try:

        load_tables_to_database(
            connection,
            datasets
        )

        create_indexes(
            connection
        )

        create_views(
            connection
        )

        validation_df = (
            validate_database(
                connection,
                datasets
            )
        )

        run_business_queries(
            connection
        )

        database_summary(
            connection
        )

        save_validation_report(
            validation_df
        )

        print_section(
            "FINAL DATABASE CHECK"
        )

        passed = (
            validation_df["status"]
            == "PASS"
        ).sum()

        print(
            f"Tables validated: "
            f"{passed}/"
            f"{len(validation_df)}"
        )

        print(
            f"Database file: "
            f"{DATABASE_FILE.name}"
        )

        print(
            "Database loading: COMPLETED"
        )

    finally:

        connection.close()

    print("\n" + "=" * 80)

    print(
        "DATABASE LOADING COMPLETED"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()