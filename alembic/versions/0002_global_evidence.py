"""Allow project and methodology evidence that is not tied to one district."""

import sqlalchemy as sa
from alembic import op


revision = "0002_global_evidence"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("evidence_chunks", "district_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM evidence_chunks WHERE district_id IS NULL")
    op.alter_column("evidence_chunks", "district_id", existing_type=sa.Integer(), nullable=False)
