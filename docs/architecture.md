# Insurance Data Engineering Platform — Architecture

```mermaid
flowchart LR

    A["Synthetic Insurance Sources<br/>Customers • Quotes • Policies<br/>Claims • Events"]

    B["Data Ingestion<br/>Schema Validation<br/>Type Conversion<br/>Metadata"]

    C["Data Quality Layer<br/>28 Validation Rules<br/>Deduplication<br/>Missing Value Remediation"]

    D["Transformation Layer<br/>Dimensions • Facts<br/>Customer 360<br/>Daily Business Summary"]

    E[("SQLite<br/>Analytics Database")]

    F["Analytical Layer<br/>5 SQL Views<br/>Indexes<br/>Business Queries"]

    G["ETL Monitoring<br/>39 Quality Checks<br/>Pipeline KPIs"]

    H["Pipeline Orchestration<br/>6 Automated ETL Steps<br/>Audit Logging"]

    I["Incremental ETL<br/>Watermarking<br/>Deduplication<br/>Incremental Loads"]

    J["Automated Testing<br/>94 Tests<br/>Schema • PK • RI<br/>Business Rules • KPIs"]

    K["GitHub Actions<br/>Automated CI Pipeline"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    E --> G

    H --> A
    H --> B
    H --> C
    H --> D
    H --> E
    H --> G

    E --> I
    I --> E

    E --> J

    K --> H
    K --> I
    K --> J
```

## Pipeline Flow

1. Synthetic insurance source data is generated.
2. Source files are ingested and schema-validated.
3. Data quality rules detect controlled source-data issues.
4. Invalid or duplicate records are remediated.
5. Clean datasets are transformed into analytical fact and dimension tables.
6. Transformed data is loaded into SQLite with indexes and analytical views.
7. Pipeline health and business KPIs are automatically monitored.
8. The complete ETL workflow is orchestrated with execution audit logs.
9. Incremental event data is processed using watermark-based loading and deduplication.
10. Automated pipeline tests validate schemas, keys, referential integrity, business rules and KPI consistency.
11. GitHub Actions executes the pipeline and tests automatically on repository changes.