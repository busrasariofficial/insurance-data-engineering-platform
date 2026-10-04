from pathlib import Path
from datetime import datetime
import subprocess
import sys
import sqlite3
import uuid
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_FILE = (
    DATABASE_DIR
    / "insurance_analytics.db"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "orchestration"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PIPELINE CONFIGURATION
# ============================================================

PIPELINE_STEPS = [
    {
        "step_order": 1,
        "step_name": "Source Data Generation",
        "script": "01_generate_insurance_data.py"
    },
    {
        "step_order": 2,
        "step_name": "Data Ingestion",
        "script": "02_data_ingestion.py"
    },
    {
        "step_order": 3,
        "step_name": "Data Quality Validation",
        "script": "03_data_quality_validation.py"
    },
    {
        "step_order": 4,
        "step_name": "Data Transformation",
        "script": "04_data_transformation.py"
    },
    {
        "step_order": 5,
        "step_name": "Database Loading",
        "script": "05_database_loading.py"
    },
    {
        "step_order": 6,
        "step_name": "ETL Pipeline Monitoring",
        "script": "06_etl_pipeline_monitoring.py"
    }
]


# ============================================================
# HELPERS
# ============================================================

def print_section(title):

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def generate_run_id():

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    short_uuid = str(
        uuid.uuid4()
    )[:8]

    return (
        f"RUN_{timestamp}_{short_uuid}"
    )


# ============================================================
# VALIDATE PIPELINE SCRIPTS
# ============================================================

def validate_scripts():

    print_section(
        "PIPELINE SCRIPT VALIDATION"
    )

    missing_scripts = []

    for step in PIPELINE_STEPS:

        script_path = (
            SRC_DIR
            / step["script"]
        )

        if script_path.exists():

            print(
                f"[OK] "
                f"{step['script']}"
            )

        else:

            print(
                f"[MISSING] "
                f"{step['script']}"
            )

            missing_scripts.append(
                step["script"]
            )

    if missing_scripts:

        raise FileNotFoundError(
            "Missing pipeline scripts: "
            + ", ".join(
                missing_scripts
            )
        )

    print(
        "\nAll pipeline scripts are available."
    )


# ============================================================
# INITIALIZE AUDIT DATABASE
# ============================================================

def initialize_audit_tables():

    print_section(
        "INITIALIZE PIPELINE AUDIT TABLES"
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        pipeline_runs (

            run_id TEXT PRIMARY KEY,

            pipeline_name TEXT,

            start_timestamp TEXT,

            end_timestamp TEXT,

            duration_seconds REAL,

            pipeline_status TEXT,

            total_steps INTEGER,

            successful_steps INTEGER,

            failed_steps INTEGER

        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        pipeline_step_runs (

            step_run_id INTEGER
            PRIMARY KEY AUTOINCREMENT,

            run_id TEXT,

            step_order INTEGER,

            step_name TEXT,

            script_name TEXT,

            start_timestamp TEXT,

            end_timestamp TEXT,

            duration_seconds REAL,

            status TEXT,

            return_code INTEGER,

            error_message TEXT

        );
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_pipeline_step_run_id
        ON pipeline_step_runs(run_id);
        """
    )

    connection.commit()
    connection.close()

    print(
        "[CREATED] pipeline_runs"
    )

    print(
        "[CREATED] pipeline_step_runs"
    )

    print(
        "[CREATED] idx_pipeline_step_run_id"
    )


# ============================================================
# RUN PIPELINE STEP
# ============================================================

def run_pipeline_step(
    run_id,
    step
):

    step_order = (
        step["step_order"]
    )

    step_name = (
        step["step_name"]
    )

    script_name = (
        step["script"]
    )

    script_path = (
        SRC_DIR
        / script_name
    )

    print_section(
        f"STEP {step_order}: "
        f"{step_name}"
    )

    print(
        f"Script: {script_name}"
    )

    start_time = (
        datetime.now()
    )

    print(
        f"Start: "
        f"{start_time}"
    )

    try:

        process = subprocess.run(
            [
                sys.executable,
                str(script_path)
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        end_time = (
            datetime.now()
        )

        duration = (
            end_time
            - start_time
        ).total_seconds()

        if process.returncode == 0:

            status = "SUCCESS"

            error_message = None

            print(
                f"Status: {status}"
            )

        else:

            status = "FAILED"

            error_message = (
                process.stderr[-2000:]
                if process.stderr
                else "Unknown error"
            )

            print(
                f"Status: {status}"
            )

            print(
                "\nError output:"
            )

            print(
                error_message
            )

        print(
            f"Duration: "
            f"{duration:.2f} seconds"
        )

        return {
            "run_id":
                run_id,

            "step_order":
                step_order,

            "step_name":
                step_name,

            "script_name":
                script_name,

            "start_timestamp":
                start_time,

            "end_timestamp":
                end_time,

            "duration_seconds":
                round(
                    duration,
                    4
                ),

            "status":
                status,

            "return_code":
                process.returncode,

            "error_message":
                error_message,

            "stdout":
                process.stdout
        }

    except Exception as exc:

        end_time = (
            datetime.now()
        )

        duration = (
            end_time
            - start_time
        ).total_seconds()

        print(
            "Status: FAILED"
        )

        print(
            f"Error: {exc}"
        )

        return {
            "run_id":
                run_id,

            "step_order":
                step_order,

            "step_name":
                step_name,

            "script_name":
                script_name,

            "start_timestamp":
                start_time,

            "end_timestamp":
                end_time,

            "duration_seconds":
                round(
                    duration,
                    4
                ),

            "status":
                "FAILED",

            "return_code":
                -1,

            "error_message":
                str(exc),

            "stdout":
                ""
        }


# ============================================================
# SAVE STEP AUDIT
# ============================================================

def save_step_audit(
    step_result
):

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO pipeline_step_runs (

            run_id,
            step_order,
            step_name,
            script_name,
            start_timestamp,
            end_timestamp,
            duration_seconds,
            status,
            return_code,
            error_message

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            step_result["run_id"],
            step_result["step_order"],
            step_result["step_name"],
            step_result["script_name"],
            str(
                step_result[
                    "start_timestamp"
                ]
            ),
            str(
                step_result[
                    "end_timestamp"
                ]
            ),
            step_result[
                "duration_seconds"
            ],
            step_result["status"],
            step_result["return_code"],
            step_result["error_message"]
        )
    )

    connection.commit()
    connection.close()


# ============================================================
# SAVE PIPELINE RUN
# ============================================================

def save_pipeline_run(
    run_id,
    start_time,
    end_time,
    step_results
):

    duration = (
        end_time
        - start_time
    ).total_seconds()

    total_steps = len(
        step_results
    )

    successful_steps = sum(
        result["status"] == "SUCCESS"
        for result in step_results
    )

    failed_steps = sum(
        result["status"] == "FAILED"
        for result in step_results
    )

    pipeline_status = (
        "SUCCESS"
        if failed_steps == 0
        else "FAILED"
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO pipeline_runs (

            run_id,
            pipeline_name,
            start_timestamp,
            end_timestamp,
            duration_seconds,
            pipeline_status,
            total_steps,
            successful_steps,
            failed_steps

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            run_id,
            "Insurance Data Engineering Pipeline",
            str(start_time),
            str(end_time),
            round(
                duration,
                4
            ),
            pipeline_status,
            total_steps,
            successful_steps,
            failed_steps
        )
    )

    connection.commit()
    connection.close()

    return {
        "pipeline_status":
            pipeline_status,

        "duration_seconds":
            duration,

        "total_steps":
            total_steps,

        "successful_steps":
            successful_steps,

        "failed_steps":
            failed_steps
    }


# ============================================================
# SAVE CSV AUDIT LOG
# ============================================================

def save_csv_audit(
    run_id,
    step_results
):

    print_section(
        "SAVE PIPELINE AUDIT LOG"
    )

    audit_records = []

    for result in step_results:

        audit_records.append({
            "run_id":
                result["run_id"],

            "step_order":
                result["step_order"],

            "step_name":
                result["step_name"],

            "script_name":
                result["script_name"],

            "start_timestamp":
                result[
                    "start_timestamp"
                ],

            "end_timestamp":
                result[
                    "end_timestamp"
                ],

            "duration_seconds":
                result[
                    "duration_seconds"
                ],

            "status":
                result["status"],

            "return_code":
                result["return_code"],

            "error_message":
                result["error_message"]
        })

    audit_df = pd.DataFrame(
        audit_records
    )

    output_path = (
        OUTPUT_DIR
        / f"{run_id}_audit_log.csv"
    )

    audit_df.to_csv(
        output_path,
        index=False
    )

    print(
        f"Audit log saved:\n"
        f"{output_path}"
    )

    return audit_df


# ============================================================
# SAVE STEP LOGS
# ============================================================

def save_step_logs(
    run_id,
    step_results
):

    logs_directory = (
        OUTPUT_DIR
        / run_id
    )

    logs_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    for result in step_results:

        log_file = (
            logs_directory
            / (
                f"{result['step_order']:02d}_"
                f"{result['script_name']}"
                ".log"
            )
        )

        with open(
            log_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                result["stdout"]
                or ""
            )

            if result[
                "error_message"
            ]:

                file.write(
                    "\n\n"
                    "ERROR\n"
                    "=====\n"
                )

                file.write(
                    result[
                        "error_message"
                    ]
                )

    print(
        f"Step logs saved:\n"
        f"{logs_directory}"
    )


# ============================================================
# PRINT PIPELINE SUMMARY
# ============================================================

def print_pipeline_summary(
    run_id,
    pipeline_summary,
    step_results
):

    print_section(
        "PIPELINE RUN SUMMARY"
    )

    print(
        f"Run ID: "
        f"{run_id}"
    )

    print(
        f"Pipeline Status: "
        f"{pipeline_summary['pipeline_status']}"
    )

    print(
        f"Total Steps: "
        f"{pipeline_summary['total_steps']}"
    )

    print(
        f"Successful Steps: "
        f"{pipeline_summary['successful_steps']}"
    )

    print(
        f"Failed Steps: "
        f"{pipeline_summary['failed_steps']}"
    )

    print(
        f"Total Duration: "
        f"{pipeline_summary['duration_seconds']:.2f} seconds"
    )

    print(
        "\nSTEP EXECUTION SUMMARY"
    )

    print(
        "-" * 80
    )

    for result in step_results:

        print(
            f"{result['step_order']}. "
            f"{result['step_name']:<30} "
            f"{result['status']:<8} "
            f"{result['duration_seconds']:>8.2f}s"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)

    print(
        "INSURANCE DATA ENGINEERING PLATFORM "
        "- PIPELINE ORCHESTRATION"
    )

    print("=" * 80)

    run_id = generate_run_id()

    pipeline_start = (
        datetime.now()
    )

    print(
        f"\nPipeline Run ID: "
        f"{run_id}"
    )

    print(
        f"Pipeline Start: "
        f"{pipeline_start}"
    )

    validate_scripts()

    initialize_audit_tables()

    step_results = []

    # ========================================================
    # EXECUTE PIPELINE
    # ========================================================

    for step in PIPELINE_STEPS:

        result = run_pipeline_step(
            run_id,
            step
        )

        step_results.append(
            result
        )

        save_step_audit(
            result
        )

        # Stop pipeline on first failed step.
        if result["status"] == "FAILED":

            print(
                "\nPipeline execution stopped "
                "because a step failed."
            )

            break

    pipeline_end = (
        datetime.now()
    )

    pipeline_summary = (
        save_pipeline_run(
            run_id,
            pipeline_start,
            pipeline_end,
            step_results
        )
    )

    save_csv_audit(
        run_id,
        step_results
    )

    save_step_logs(
        run_id,
        step_results
    )

    print_pipeline_summary(
        run_id,
        pipeline_summary,
        step_results
    )

    print("\n" + "=" * 80)

    print(
        "PIPELINE ORCHESTRATION COMPLETED"
    )

    print("=" * 80)

    # Make failed pipeline visible to CI/CD systems.
    if (
        pipeline_summary[
            "pipeline_status"
        ]
        == "FAILED"
    ):

        sys.exit(1)


if __name__ == "__main__":
    main()