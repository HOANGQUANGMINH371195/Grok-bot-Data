# Versioned R1 fixtures

Fixtures are synthetic and safe to commit. The CSVs exercise UTF-8, quoted multiline
fields, nulls, PII classification and adversarial text. Expected JSON is canonical
test output, not a runtime data source. Binary Parquet and large-cap tests are added
by the data owner with the same fixture-version and SHA-256 convention.
