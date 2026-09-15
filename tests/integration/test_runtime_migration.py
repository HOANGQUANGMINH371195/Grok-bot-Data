from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg")


def test_runtime_schema_is_migrated_and_force_rls_is_enabled() -> None:
    url = os.environ.get("VDA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("VDA_TEST_DATABASE_URL is required for PostgreSQL integration")

    psycopg_url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(psycopg_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        assert cursor.fetchone() == ("0006_run_events",)
        cursor.execute(
            """
            SELECT tablename, rowsecurity, relforcerowsecurity
            FROM pg_tables
            JOIN pg_class ON pg_class.relname = pg_tables.tablename
            WHERE schemaname = 'public'
              AND tablename = ANY(%s)
            ORDER BY tablename
            """,
            [["tasks", "runs", "attempts", "tool_executions", "effects", "run_events"]],
        )
        rows = cursor.fetchall()
        assert rows == [
            ("attempts", True, True),
            ("effects", True, True),
            ("run_events", True, True),
            ("runs", True, True),
            ("tasks", True, True),
            ("tool_executions", True, True),
        ]
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conname = ANY(%s) ORDER BY conname",
            [[
                "runs_workspace_task_fk",
                "attempts_workspace_run_fk",
                "tool_executions_workspace_run_fk",
                "tool_executions_workspace_attempt_fk",
                "effects_workspace_run_fk",
                "effects_workspace_attempt_fk",
                "run_events_workspace_run_fk",
                "run_events_workspace_attempt_fk",
            ]],
        )
        assert [row[0] for row in cursor.fetchall()] == [
            "attempts_workspace_run_fk",
            "effects_workspace_attempt_fk",
            "effects_workspace_run_fk",
            "run_events_workspace_attempt_fk",
            "run_events_workspace_run_fk",
            "runs_workspace_task_fk",
            "tool_executions_workspace_attempt_fk",
            "tool_executions_workspace_run_fk",
        ]
