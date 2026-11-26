"""Add atomic, versioned historical evidence releases without modifying scores."""
from alembic import op

revision = '0007_historical_evidence'
down_revision = '0006_sessions_observability'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE TABLE IF NOT EXISTS historical_releases (id VARCHAR(80) PRIMARY KEY, payload JSONB NOT NULL)')


def downgrade():
    op.drop_table('historical_releases')
