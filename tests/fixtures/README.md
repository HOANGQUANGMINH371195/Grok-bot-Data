# Versioned R1 fixtures

Fixtures are synthetic and safe to commit. The CSVs exercise UTF-8, quoted multiline
fields, nulls, Decimal-as-string conversion, PII classification and adversarial text.
Expected JSON is canonical test output, not a runtime data source. The pinned Parquet
fixture is `data/flat_small.parquet` (SHA-256
`9fadeb1287486298247ab5974f35c537aecfb75380dea56f0cc382fc45005ec4`) and is flat,
synthetic, and uncompressed. Tests verify its shape/hash and reject nested types.
