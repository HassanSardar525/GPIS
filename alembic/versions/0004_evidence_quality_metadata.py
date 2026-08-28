"""Add observation comparability and score-quality metadata."""

from alembic import op


revision = "0004_evidence_quality"
down_revision = "0003_trace_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 creates from current model metadata, so IF NOT EXISTS also supports
    # a brand-new database upgraded directly to head.
    op.execute(
        "ALTER TABLE observations ADD COLUMN IF NOT EXISTS "
        "definition_version VARCHAR(80) NOT NULL DEFAULT 'prototype-v1'"
    )
    op.execute(
        "ALTER TABLE observations ADD COLUMN IF NOT EXISTS "
        "geography_level VARCHAR(40) NOT NULL DEFAULT 'district'"
    )
    op.execute("ALTER TABLE observations ADD COLUMN IF NOT EXISTS population_basis VARCHAR(160)")
    op.execute("ALTER TABLE observations ADD COLUMN IF NOT EXISTS comparability_group VARCHAR(120)")
    op.execute(
        "ALTER TABLE observations ADD COLUMN IF NOT EXISTS "
        "quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_observations_comparability_group "
        "ON observations (comparability_group)"
    )

    op.execute(
        "ALTER TABLE score_results ADD COLUMN IF NOT EXISTS "
        "reporting_period VARCHAR(160) NOT NULL DEFAULT 'mixed-current-period'"
    )
    op.execute("ALTER TABLE score_results ADD COLUMN IF NOT EXISTS confidence NUMERIC(5, 4)")
    op.execute(
        "ALTER TABLE score_results ADD COLUMN IF NOT EXISTS "
        "missing_components JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE score_results ADD COLUMN IF NOT EXISTS "
        "warnings JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE score_results DROP COLUMN IF EXISTS warnings")
    op.execute("ALTER TABLE score_results DROP COLUMN IF EXISTS missing_components")
    op.execute("ALTER TABLE score_results DROP COLUMN IF EXISTS confidence")
    op.execute("ALTER TABLE score_results DROP COLUMN IF EXISTS reporting_period")
    op.execute("DROP INDEX IF EXISTS ix_observations_comparability_group")
    op.execute("ALTER TABLE observations DROP COLUMN IF EXISTS quality_flags")
    op.execute("ALTER TABLE observations DROP COLUMN IF EXISTS comparability_group")
    op.execute("ALTER TABLE observations DROP COLUMN IF EXISTS population_basis")
    op.execute("ALTER TABLE observations DROP COLUMN IF EXISTS geography_level")
    op.execute("ALTER TABLE observations DROP COLUMN IF EXISTS definition_version")
