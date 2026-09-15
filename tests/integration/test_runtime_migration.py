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
        assert cursor.fetchone() == ("0004_runtime",)
        cursor.execute(
            """
            SELECT tablename, rowsecurity, relforcerowsecurity
            FROM pg_tables
            JOIN pg_class ON pg_class.relname = pg_tables.tablename
            WHERE schemaname = 'public'
              AND tablename = ANY(%s)
            ORDER BY tablename
            """,
            [["tasks", "runs", "attempts", "tool_executions", "effects"]],
        )
        rows = cursor.fetchall()
        assert rows == [
            ("attempts", True, True),
            ("effects", True, True),
            ("runs", True, True),
            ("tasks", True, True),
            ("tool_executions", True, True),
        ]
