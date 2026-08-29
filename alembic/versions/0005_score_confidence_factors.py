"""Store deterministic score confidence factors."""

from alembic import op


revision = "0005_confidence_factors"
down_revision = "0004_evidence_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE score_results ADD COLUMN IF NOT EXISTS "
        "confidence_factors JSONB NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE score_results DROP COLUMN IF EXISTS confidence_factors")
