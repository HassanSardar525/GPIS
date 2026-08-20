"""Store retrieval ranks, generation mode, citations, and warnings with each trace."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0003_trace_details"
down_revision = "0002_global_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_traces",
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("retrieval_traces", "details")
