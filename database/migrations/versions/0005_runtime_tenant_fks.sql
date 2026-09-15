-- Expand-only tenant integrity hardening for runtime references.
-- Existing single-column FKs remain for clear database errors; composite FKs
-- prevent a valid ID from crossing workspace boundaries.
ALTER TABLE tasks
  ADD CONSTRAINT tasks_workspace_id_id_key UNIQUE (workspace_id, id);
ALTER TABLE runs
  ADD CONSTRAINT runs_workspace_id_id_key UNIQUE (workspace_id, id);
ALTER TABLE attempts
  ADD CONSTRAINT attempts_workspace_id_id_key UNIQUE (workspace_id, id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'runs_workspace_task_fk'
  ) THEN
    ALTER TABLE runs
      ADD CONSTRAINT runs_workspace_task_fk
      FOREIGN KEY (workspace_id, task_id) REFERENCES tasks (workspace_id, id);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'attempts_workspace_run_fk'
  ) THEN
    ALTER TABLE attempts
      ADD CONSTRAINT attempts_workspace_run_fk
      FOREIGN KEY (workspace_id, run_id) REFERENCES runs (workspace_id, id);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tool_executions_workspace_run_fk'
  ) THEN
    ALTER TABLE tool_executions
      ADD CONSTRAINT tool_executions_workspace_run_fk
      FOREIGN KEY (workspace_id, run_id) REFERENCES runs (workspace_id, id);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tool_executions_workspace_attempt_fk'
  ) THEN
    ALTER TABLE tool_executions
      ADD CONSTRAINT tool_executions_workspace_attempt_fk
      FOREIGN KEY (workspace_id, attempt_id) REFERENCES attempts (workspace_id, id);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'effects_workspace_run_fk'
  ) THEN
    ALTER TABLE effects
      ADD CONSTRAINT effects_workspace_run_fk
      FOREIGN KEY (workspace_id, run_id) REFERENCES runs (workspace_id, id);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'effects_workspace_attempt_fk'
  ) THEN
    ALTER TABLE effects
      ADD CONSTRAINT effects_workspace_attempt_fk
      FOREIGN KEY (workspace_id, attempt_id) REFERENCES attempts (workspace_id, id);
  END IF;
END $$;
