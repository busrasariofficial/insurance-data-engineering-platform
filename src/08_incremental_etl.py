from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import uuid

import numpy as np
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

INCREMENTAL_DIR = (
    PROJECT_ROOT
    / "data"
    / "incremental"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "incremental"
)

INCREMENTAL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

RANDOM_SEED = 42

PIPELINE_NAME = (
    "insurance_event_incremental_load"
)


# ============================================================
# HELPERS
# ============================================================

def print_section(title):

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def generate_batch_id():

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    short_uuid = str(
        uuid.uuid4()
    )[:8]

    return (
        f"BATCH_{timestamp}_{short_uuid}"
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
# INITIALIZE INCREMENTAL METADATA
# ============================================================

def initialize_incremental_metadata(
    connection
):

    print_section(
        "INITIALIZE INCREMENTAL METADATA"
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        etl_watermarks (

            pipeline_name TEXT PRIMARY KEY,

            watermark_column TEXT,

            last_watermark TEXT,

            updated_timestamp TEXT

        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        incremental_load_audit (

            audit_id INTEGER
            PRIMARY KEY AUTOINCREMENT,

            batch_id TEXT,

            pipeline_name TEXT,

            source_rows INTEGER,

            new_rows INTEGER,

            duplicate_rows INTEGER,

            inserted_rows INTEGER,

            updated_rows INTEGER,

            previous_watermark TEXT,

            new_watermark TEXT,

            load_status TEXT,

            start_timestamp TEXT,

            end_timestamp TEXT,

            duration_seconds REAL

        );
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_incremental_batch_id
        ON incremental_load_audit(batch_id);
        """
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM etl_watermarks
        WHERE pipeline_name = ?;
        """,
        (
            PIPELINE_NAME,
        )
    )

    exists = (
        cursor.fetchone()[0]
    )

    if exists == 0:

        current_max_timestamp = (
            cursor.execute(
                """
                SELECT MAX(event_timestamp)
                FROM fact_events;
                """
            ).fetchone()[0]
        )

        cursor.execute(
            """
            INSERT INTO etl_watermarks (

                pipeline_name,
                watermark_column,
                last_watermark,
                updated_timestamp

            )

            VALUES (?, ?, ?, ?);
            """,
            (
                PIPELINE_NAME,
                "event_timestamp",
                current_max_timestamp,
                str(datetime.now())
            )
        )

        print(
            "[CREATED] Initial watermark"
        )

        print(
            f"Initial watermark: "
            f"{current_max_timestamp}"
        )

    else:

        print(
            "[OK] Existing watermark found"
        )

    connection.commit()


# ============================================================
# GET WATERMARK
# ============================================================

def get_watermark(
    connection
):

    print_section(
        "READ CURRENT WATERMARK"
    )

    result = connection.execute(
        """
        SELECT last_watermark
        FROM etl_watermarks
        WHERE pipeline_name = ?;
        """,
        (
            PIPELINE_NAME,
        )
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Watermark could not be found."
        )

    watermark = pd.to_datetime(
        result[0]
    )

    print(
        f"Current watermark: "
        f"{watermark}"
    )

    return watermark


# ============================================================
# GET NEXT EVENT NUMBER
# ============================================================

def get_next_event_number(
    connection
):

    print_section(
        "EVENT ID SEQUENCE CHECK"
    )

    event_ids = pd.read_sql_query(
        """
        SELECT event_id
        FROM fact_events;
        """,
        connection
    )

    if event_ids.empty:

        print(
            "No existing event IDs found."
        )

        print(
            "Next event number: 1"
        )

        return 1

    extracted_numbers = (
        event_ids["event_id"]
        .astype(str)
        .str.extract(
            r"(\d+)$",
            expand=False
        )
    )

    numeric_ids = pd.to_numeric(
        extracted_numbers,
        errors="coerce"
    )

    valid_numeric_ids = (
        numeric_ids.dropna()
    )

    if valid_numeric_ids.empty:

        raise ValueError(
            "Existing event IDs do not contain "
            "a valid numeric suffix."
        )

    max_event_number = int(
        valid_numeric_ids.max()
    )

    next_event_number = (
        max_event_number + 1
    )

    print(
        f"Highest existing event number: "
        f"{max_event_number:,}"
    )

    print(
        f"Next event number: "
        f"{next_event_number:,}"
    )

    return next_event_number


# ============================================================
# GENERATE INCREMENTAL EVENT BATCH
# ============================================================

def generate_incremental_batch(
    connection,
    watermark,
    batch_id
):

    print_section(
        "GENERATE INCREMENTAL SOURCE BATCH"
    )

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    customers = pd.read_sql_query(
        """
        SELECT customer_id
        FROM dim_customer;
        """,
        connection
    )

    if customers.empty:

        raise RuntimeError(
            "dim_customer is empty."
        )

    next_event_number = (
        get_next_event_number(
            connection
        )
    )

    # --------------------------------------------------------
    # NEW RECORDS
    # --------------------------------------------------------

    new_record_count = 5000

    new_event_numbers = range(
        next_event_number,
        next_event_number
        + new_record_count
    )

    new_event_ids = [
        f"EVT_{event_number:08d}"
        for event_number
        in new_event_numbers
    ]

    customer_ids = rng.choice(
        customers[
            "customer_id"
        ].values,
        size=new_record_count,
        replace=True
    )

    event_types = rng.choice(
        [
            "page_view",
            "quote_started",
            "quote_completed",
            "policy_viewed",
            "login"
        ],
        size=new_record_count,
        p=[
            0.45,
            0.18,
            0.12,
            0.10,
            0.15
        ]
    )

    device_types = rng.choice(
        [
            "Desktop",
            "Mobile",
            "Tablet"
        ],
        size=new_record_count,
        p=[
            0.40,
            0.50,
            0.10
        ]
    )

    # All new records are generated
    # after the current watermark.
    random_minutes = rng.integers(
        low=1,
        high=7 * 24 * 60,
        size=new_record_count
    )

    event_timestamps = [
        watermark
        + timedelta(
            minutes=int(minutes)
        )
        for minutes
        in random_minutes
    ]

    new_events = pd.DataFrame({
        "event_id":
            new_event_ids,

        "customer_id":
            customer_ids,

        "event_type":
            event_types,

        "device_type":
            device_types,

        "event_timestamp":
            event_timestamps
    })

    # --------------------------------------------------------
    # CONTROLLED DUPLICATES
    # --------------------------------------------------------

    duplicate_count = 50

    existing_events = pd.read_sql_query(
        """
        SELECT
            event_id,
            customer_id,
            event_type,
            device_type,
            event_timestamp

        FROM fact_events

        ORDER BY event_timestamp DESC

        LIMIT 50;
        """,
        connection
    )

    actual_duplicate_count = len(
        existing_events
    )

    source_batch = pd.concat(
        [
            new_events,
            existing_events
        ],
        ignore_index=True
    )

    source_batch = (
        source_batch
        .sample(
            frac=1,
            random_state=RANDOM_SEED
        )
        .reset_index(
            drop=True
        )
    )

    output_file = (
        INCREMENTAL_DIR
        / f"{batch_id}_events.csv"
    )

    source_batch.to_csv(
        output_file,
        index=False
    )

    print(
        f"New records generated: "
        f"{new_record_count:,}"
    )

    print(
        f"Controlled duplicates added: "
        f"{actual_duplicate_count:,}"
    )

    print(
        f"Source batch rows: "
        f"{len(source_batch):,}"
    )

    print(
        f"First new event ID: "
        f"{new_event_ids[0]}"
    )

    print(
        f"Last new event ID: "
        f"{new_event_ids[-1]}"
    )

    print(
        "\nIncremental source saved:"
    )

    print(
        output_file
    )

    return source_batch


# ============================================================
# VALIDATE INCREMENTAL SOURCE
# ============================================================

def validate_incremental_source(
    source_batch
):

    print_section(
        "INCREMENTAL SOURCE VALIDATION"
    )

    required_columns = [
        "event_id",
        "customer_id",
        "event_type",
        "device_type",
        "event_timestamp"
    ]

    missing_columns = [
        column
        for column
        in required_columns
        if column
        not in source_batch.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing source columns: "
            + ", ".join(
                missing_columns
            )
        )

    source_batch = (
        source_batch.copy()
    )

    source_batch[
        "event_timestamp"
    ] = pd.to_datetime(
        source_batch[
            "event_timestamp"
        ],
        errors="coerce"
    )

    missing_ids = int(
        source_batch[
            "event_id"
        ]
        .isna()
        .sum()
    )

    invalid_timestamps = int(
        source_batch[
            "event_timestamp"
        ]
        .isna()
        .sum()
    )

    print(
        f"Missing event IDs: "
        f"{missing_ids:,}"
    )

    print(
        f"Invalid timestamps: "
        f"{invalid_timestamps:,}"
    )

    if (
        missing_ids > 0
        or invalid_timestamps > 0
    ):

        raise ValueError(
            "Incremental source "
            "validation failed."
        )

    print(
        "Incremental source validation: PASS"
    )

    return source_batch


# ============================================================
# IDENTIFY INCREMENTAL RECORDS
# ============================================================

def identify_incremental_records(
    connection,
    source_batch,
    watermark
):

    print_section(
        "WATERMARK AND DUPLICATE FILTERING"
    )

    source_batch = (
        source_batch.copy()
    )

    source_batch[
        "event_timestamp"
    ] = pd.to_datetime(
        source_batch[
            "event_timestamp"
        ]
    )

    # --------------------------------------------------------
    # WATERMARK FILTER
    # --------------------------------------------------------

    after_watermark = (
        source_batch[
            source_batch[
                "event_timestamp"
            ]
            > watermark
        ]
        .copy()
    )

    watermark_rejected = (
        len(source_batch)
        - len(after_watermark)
    )

    print(
        f"Source rows: "
        f"{len(source_batch):,}"
    )

    print(
        f"Rows after watermark: "
        f"{len(after_watermark):,}"
    )

    print(
        f"Rows rejected by watermark: "
        f"{watermark_rejected:,}"
    )

    # --------------------------------------------------------
    # TARGET DUPLICATE CHECK
    # --------------------------------------------------------

    existing_ids = pd.read_sql_query(
        """
        SELECT event_id
        FROM fact_events;
        """,
        connection
    )

    existing_id_set = set(
        existing_ids[
            "event_id"
        ]
        .astype(str)
    )

    after_watermark[
        "_event_id_key"
    ] = (
        after_watermark[
            "event_id"
        ]
        .astype(str)
    )

    existing_duplicate_mask = (
        after_watermark[
            "_event_id_key"
        ]
        .isin(
            existing_id_set
        )
    )

    existing_duplicate_count = int(
        existing_duplicate_mask.sum()
    )

    candidate_rows = (
        after_watermark[
            ~existing_duplicate_mask
        ]
        .copy()
    )

    # --------------------------------------------------------
    # INTERNAL BATCH DUPLICATE CHECK
    # --------------------------------------------------------

    internal_duplicate_mask = (
        candidate_rows[
            "_event_id_key"
        ]
        .duplicated(
            keep="first"
        )
    )

    internal_duplicate_count = int(
        internal_duplicate_mask.sum()
    )

    new_rows = (
        candidate_rows[
            ~internal_duplicate_mask
        ]
        .copy()
    )

    new_rows = (
        new_rows.drop(
            columns=[
                "_event_id_key"
            ]
        )
    )

    total_duplicate_rows = (
        watermark_rejected
        + existing_duplicate_count
        + internal_duplicate_count
    )

    print(
        f"Existing-ID duplicates rejected: "
        f"{existing_duplicate_count:,}"
    )

    print(
        f"Internal batch duplicates rejected: "
        f"{internal_duplicate_count:,}"
    )

    print(
        f"Total rejected duplicate/old rows: "
        f"{total_duplicate_rows:,}"
    )

    print(
        f"Records eligible for insert: "
        f"{len(new_rows):,}"
    )

    return (
        new_rows,
        total_duplicate_rows
    )


# ============================================================
# TRANSFORM NEW EVENTS
# ============================================================

def transform_incremental_events(
    new_rows
):

    print_section(
        "TRANSFORM INCREMENTAL RECORDS"
    )

    transformed = (
        new_rows.copy()
    )

    if transformed.empty:

        print(
            "No records require transformation."
        )

        return transformed

    transformed[
        "event_timestamp"
    ] = pd.to_datetime(
        transformed[
            "event_timestamp"
        ]
    )

    transformed[
        "event_date"
    ] = (
        transformed[
            "event_timestamp"
        ].dt.date
    )

    transformed[
        "event_year"
    ] = (
        transformed[
            "event_timestamp"
        ].dt.year
    )

    transformed[
        "event_month"
    ] = (
        transformed[
            "event_timestamp"
        ].dt.month
    )

    transformed[
        "event_day"
    ] = (
        transformed[
            "event_timestamp"
        ].dt.day
    )

    transformed[
        "event_hour"
    ] = (
        transformed[
            "event_timestamp"
        ].dt.hour
    )

    transformed[
        "event_day_of_week"
    ] = (
        transformed[
            "event_timestamp"
        ].dt.day_name()
    )

    transformed[
        "is_mobile"
    ] = (
        transformed[
            "device_type"
        ]
        .eq("Mobile")
        .astype(int)
    )

    target_columns = [
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

    transformed = (
        transformed[
            target_columns
        ]
        .copy()
    )

    print(
        f"Transformed rows: "
        f"{len(transformed):,}"
    )

    print(
        f"Transformed columns: "
        f"{len(transformed.columns)}"
    )

    return transformed


# ============================================================
# REFERENTIAL INTEGRITY CHECK
# ============================================================

def validate_customer_references(
    connection,
    transformed
):

    print_section(
        "INCREMENTAL REFERENTIAL INTEGRITY"
    )

    if transformed.empty:

        print(
            "No records to validate."
        )

        return

    customers = pd.read_sql_query(
        """
        SELECT customer_id
        FROM dim_customer;
        """,
        connection
    )

    valid_customers = set(
        customers[
            "customer_id"
        ]
        .astype(str)
    )

    invalid_mask = (
        ~transformed[
            "customer_id"
        ]
        .astype(str)
        .isin(
            valid_customers
        )
    )

    invalid_count = int(
        invalid_mask.sum()
    )

    print(
        f"Invalid customer references: "
        f"{invalid_count:,}"
    )

    if invalid_count > 0:

        raise ValueError(
            "Incremental batch contains "
            "invalid customer references."
        )

    print(
        "Referential integrity: PASS"
    )


# ============================================================
# APPEND NEW RECORDS
# ============================================================

def append_incremental_records(
    connection,
    transformed
):

    print_section(
        "APPEND INCREMENTAL RECORDS"
    )

    if transformed.empty:

        print(
            "No new records to insert."
        )

        return 0

    before_count = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_events;
            """
        ).fetchone()[0]
    )

    transformed_to_load = (
        transformed.copy()
    )

    transformed_to_load[
        "event_timestamp"
    ] = (
        transformed_to_load[
            "event_timestamp"
        ]
        .astype(str)
    )

    transformed_to_load[
        "event_date"
    ] = (
        transformed_to_load[
            "event_date"
        ]
        .astype(str)
    )

    transformed_to_load.to_sql(
        "fact_events",
        connection,
        if_exists="append",
        index=False,
        chunksize=1000
    )

    connection.commit()

    after_count = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM fact_events;
            """
        ).fetchone()[0]
    )

    inserted_rows = (
        after_count
        - before_count
    )

    print(
        f"Rows before load: "
        f"{before_count:,}"
    )

    print(
        f"Rows after load: "
        f"{after_count:,}"
    )

    print(
        f"Inserted rows: "
        f"{inserted_rows:,}"
    )

    if inserted_rows != len(
        transformed
    ):

        raise RuntimeError(
            "Inserted row count does not "
            "match transformed row count."
        )

    return inserted_rows


# ============================================================
# UPDATE WATERMARK
# ============================================================

def update_watermark(
    connection,
    transformed,
    previous_watermark
):

    print_section(
        "UPDATE WATERMARK"
    )

    if transformed.empty:

        print(
            "No new records. "
            "Watermark unchanged."
        )

        return previous_watermark

    new_watermark = pd.to_datetime(
        transformed[
            "event_timestamp"
        ].max()
    )

    connection.execute(
        """
        UPDATE etl_watermarks

        SET
            last_watermark = ?,
            updated_timestamp = ?

        WHERE pipeline_name = ?;
        """,
        (
            str(new_watermark),
            str(datetime.now()),
            PIPELINE_NAME
        )
    )

    connection.commit()

    print(
        f"Previous watermark: "
        f"{previous_watermark}"
    )

    print(
        f"New watermark: "
        f"{new_watermark}"
    )

    return new_watermark


# ============================================================
# VALIDATE FINAL LOAD
# ============================================================

def validate_final_load(
    connection,
    transformed
):

    print_section(
        "POST-LOAD VALIDATION"
    )

    if transformed.empty:

        print(
            "No new records were loaded."
        )

        print(
            "Post-load validation: PASS"
        )

        return

    loaded_ids = (
        transformed[
            "event_id"
        ]
        .astype(str)
        .tolist()
    )

    placeholders = ",".join(
        ["?"]
        * len(loaded_ids)
    )

    loaded_count = (
        connection.execute(
            f"""
            SELECT COUNT(*)
            FROM fact_events
            WHERE event_id IN (
                {placeholders}
            );
            """,
            loaded_ids
        ).fetchone()[0]
    )

    duplicate_count = (
        connection.execute(
            """
            SELECT COUNT(*)

            FROM (

                SELECT
                    event_id,
                    COUNT(*) AS record_count

                FROM fact_events

                GROUP BY event_id

                HAVING COUNT(*) > 1

            );
            """
        ).fetchone()[0]
    )

    print(
        f"Expected inserted records: "
        f"{len(transformed):,}"
    )

    print(
        f"Verified inserted records: "
        f"{loaded_count:,}"
    )

    print(
        f"Duplicate event IDs in target: "
        f"{duplicate_count:,}"
    )

    if loaded_count != len(
        transformed
    ):

        raise RuntimeError(
            "Inserted record verification failed."
        )

    if duplicate_count > 0:

        raise RuntimeError(
            "Duplicate event IDs detected "
            "in target table."
        )

    print(
        "Post-load validation: PASS"
    )


# ============================================================
# SAVE AUDIT RECORD
# ============================================================

def save_audit_record(
    connection,
    batch_id,
    source_rows,
    new_rows,
    duplicate_rows,
    inserted_rows,
    previous_watermark,
    new_watermark,
    start_time,
    status
):

    end_time = (
        datetime.now()
    )

    duration = (
        end_time
        - start_time
    ).total_seconds()

    connection.execute(
        """
        INSERT INTO incremental_load_audit (

            batch_id,
            pipeline_name,
            source_rows,
            new_rows,
            duplicate_rows,
            inserted_rows,
            updated_rows,
            previous_watermark,
            new_watermark,
            load_status,
            start_timestamp,
            end_timestamp,
            duration_seconds

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        );
        """,
        (
            batch_id,
            PIPELINE_NAME,
            source_rows,
            new_rows,
            duplicate_rows,
            inserted_rows,
            0,
            str(previous_watermark),
            str(new_watermark),
            status,
            str(start_time),
            str(end_time),
            round(
                duration,
                4
            )
        )
    )

    connection.commit()

    return duration


# ============================================================
# SAVE BATCH SUMMARY
# ============================================================

def save_batch_summary(
    batch_id,
    source_rows,
    new_rows,
    duplicate_rows,
    inserted_rows,
    previous_watermark,
    new_watermark,
    duration,
    status
):

    summary = pd.DataFrame(
        [
            {
                "batch_id":
                    batch_id,

                "pipeline_name":
                    PIPELINE_NAME,

                "source_rows":
                    source_rows,

                "new_rows":
                    new_rows,

                "duplicate_rows":
                    duplicate_rows,

                "inserted_rows":
                    inserted_rows,

                "updated_rows":
                    0,

                "previous_watermark":
                    previous_watermark,

                "new_watermark":
                    new_watermark,

                "duration_seconds":
                    duration,

                "status":
                    status
            }
        ]
    )

    output_file = (
        OUTPUT_DIR
        / f"{batch_id}_summary.csv"
    )

    summary.to_csv(
        output_file,
        index=False
    )

    print(
        "\nBatch summary saved:"
    )

    print(
        output_file
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

def print_final_summary(
    batch_id,
    source_rows,
    new_rows,
    duplicate_rows,
    inserted_rows,
    previous_watermark,
    new_watermark,
    duration
):

    print_section(
        "INCREMENTAL LOAD SUMMARY"
    )

    print(
        f"Batch ID: "
        f"{batch_id}"
    )

    print(
        f"Source rows: "
        f"{source_rows:,}"
    )

    print(
        f"Eligible new rows: "
        f"{new_rows:,}"
    )

    print(
        f"Rejected old/duplicate rows: "
        f"{duplicate_rows:,}"
    )

    print(
        f"Inserted rows: "
        f"{inserted_rows:,}"
    )

    print(
        f"Previous watermark: "
        f"{previous_watermark}"
    )

    print(
        f"New watermark: "
        f"{new_watermark}"
    )

    print(
        f"Duration: "
        f"{duration:.2f} seconds"
    )

    print(
        "Load status: SUCCESS"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)

    print(
        "INSURANCE DATA ENGINEERING PLATFORM "
        "- INCREMENTAL ETL"
    )

    print("=" * 80)

    batch_id = (
        generate_batch_id()
    )

    start_time = (
        datetime.now()
    )

    print(
        f"\nBatch ID: "
        f"{batch_id}"
    )

    print(
        f"Batch Start: "
        f"{start_time}"
    )

    connection = (
        connect_database()
    )

    try:

        initialize_incremental_metadata(
            connection
        )

        previous_watermark = (
            get_watermark(
                connection
            )
        )

        source_batch = (
            generate_incremental_batch(
                connection,
                previous_watermark,
                batch_id
            )
        )

        source_batch = (
            validate_incremental_source(
                source_batch
            )
        )

        (
            new_rows,
            duplicate_rows
        ) = identify_incremental_records(
            connection,
            source_batch,
            previous_watermark
        )

        transformed = (
            transform_incremental_events(
                new_rows
            )
        )

        validate_customer_references(
            connection,
            transformed
        )

        inserted_rows = (
            append_incremental_records(
                connection,
                transformed
            )
        )

        new_watermark = (
            update_watermark(
                connection,
                transformed,
                previous_watermark
            )
        )

        validate_final_load(
            connection,
            transformed
        )

        duration = (
            save_audit_record(
                connection=connection,
                batch_id=batch_id,
                source_rows=len(
                    source_batch
                ),
                new_rows=len(
                    transformed
                ),
                duplicate_rows=duplicate_rows,
                inserted_rows=inserted_rows,
                previous_watermark=previous_watermark,
                new_watermark=new_watermark,
                start_time=start_time,
                status="SUCCESS"
            )
        )

        save_batch_summary(
            batch_id=batch_id,
            source_rows=len(
                source_batch
            ),
            new_rows=len(
                transformed
            ),
            duplicate_rows=duplicate_rows,
            inserted_rows=inserted_rows,
            previous_watermark=previous_watermark,
            new_watermark=new_watermark,
            duration=duration,
            status="SUCCESS"
        )

        print_final_summary(
            batch_id=batch_id,
            source_rows=len(
                source_batch
            ),
            new_rows=len(
                transformed
            ),
            duplicate_rows=duplicate_rows,
            inserted_rows=inserted_rows,
            previous_watermark=previous_watermark,
            new_watermark=new_watermark,
            duration=duration
        )

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()

    print("\n" + "=" * 80)

    print(
        "INCREMENTAL ETL COMPLETED"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()