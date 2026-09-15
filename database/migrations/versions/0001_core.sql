-- M0 contract migration chain seed. Application tables are added by M1 owners.
CREATE TABLE IF NOT EXISTS schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations(version) VALUES ('0001_core') ON CONFLICT DO NOTHING;
