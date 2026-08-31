"""Persist chat sessions and privacy-safe telemetry metadata."""

from alembic import op


revision = "0006_sessions_observability"
down_revision = "0005_confidence_factors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id VARCHAR(100) PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL,
            last_activity_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            message_count INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'active'
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_sessions_last_activity_at ON chat_sessions (last_activity_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_sessions_expires_at ON chat_sessions (expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_sessions_status ON chat_sessions (status)")
    op.execute("ALTER TABLE retrieval_traces ADD COLUMN IF NOT EXISTS session_id VARCHAR(100)")
    op.execute("ALTER TABLE retrieval_traces ADD COLUMN IF NOT EXISTS outcome VARCHAR(30) NOT NULL DEFAULT 'success'")
    op.execute("ALTER TABLE retrieval_traces ADD COLUMN IF NOT EXISTS provider_status VARCHAR(40) NOT NULL DEFAULT 'unknown'")
    op.execute("ALTER TABLE retrieval_traces ADD COLUMN IF NOT EXISTS failure_category VARCHAR(60)")
    op.execute("UPDATE retrieval_traces SET question = ''")
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrieval_traces_session_id ON retrieval_traces (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrieval_traces_outcome ON retrieval_traces (outcome)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrieval_traces_provider_status ON retrieval_traces (provider_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrieval_traces_failure_category ON retrieval_traces (failure_category)")
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE retrieval_traces ADD CONSTRAINT fk_retrieval_traces_session
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE retrieval_traces DROP CONSTRAINT IF EXISTS fk_retrieval_traces_session")
    for column in ("failure_category", "provider_status", "outcome", "session_id"):
        op.execute(f"ALTER TABLE retrieval_traces DROP COLUMN IF EXISTS {column}")
    op.execute("DROP TABLE IF EXISTS chat_sessions")
