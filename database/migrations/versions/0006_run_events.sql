-- Metadata-only durable runtime journal. Raw prompts, content and secrets are
-- rejected by the repository boundary before this table is written.
CREATE TABLE IF NOT EXISTS run_events (
  id text PRIMARY KEY,
  workspace_id text NOT NULL REFERENCES workspaces(id),
  run_id text NOT NULL,
  attempt_id text,
  event_key text NOT NULL,
  event_type text NOT NULL,
  metadata_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, event_key),
  CONSTRAINT run_events_workspace_run_fk
    FOREIGN KEY (workspace_id, run_id) REFERENCES runs (workspace_id, id),
  CONSTRAINT run_events_workspace_attempt_fk
    FOREIGN KEY (workspace_id, attempt_id) REFERENCES attempts (workspace_id, id)
);

CREATE INDEX IF NOT EXISTS run_events_run_idx
  ON run_events(workspace_id, run_id, created_at, id);

ALTER TABLE run_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS run_events_workspace_scope ON run_events;
CREATE POLICY run_events_workspace_scope ON run_events
  USING (workspace_id = current_setting('app.workspace_id', true));
