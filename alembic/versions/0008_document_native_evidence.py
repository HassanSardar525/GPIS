"""Add provenance for document-native, structure-aware evidence chunks."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_document_native_evidence"
down_revision = "0007_historical_evidence"
branch_labels = None
depends_on = None


def upgrade():
    # 0001 intentionally creates from current ORM metadata. These guards make
    # the additive migration work for both legacy databases and fresh installs.
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("evidence_chunks")}
    columns = {
        "chunk_type": sa.Column("chunk_type", sa.String(40), nullable=True),
        "parent_id": sa.Column("parent_id", sa.String(160), nullable=True),
        "page_number": sa.Column("page_number", sa.Integer(), nullable=True),
        "table_reference": sa.Column("table_reference", sa.String(160), nullable=True),
        "source_checksum": sa.Column("source_checksum", sa.String(64), nullable=True),
        "parser_version": sa.Column("parser_version", sa.String(80), nullable=True),
        "content_hash": sa.Column("content_hash", sa.String(64), nullable=True),
        "extraction_metadata": sa.Column(
            "extraction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    }
    for name, column in columns.items():
        if name not in existing_columns:
            op.add_column("evidence_chunks", column)

    inspector = sa.inspect(op.get_bind())
    parent_fk_exists = any(
        foreign_key.get("constrained_columns") == ["parent_id"]
        for foreign_key in inspector.get_foreign_keys("evidence_chunks")
    )
    if not parent_fk_exists:
        op.create_foreign_key(
            "fk_evidence_chunks_parent_id",
            "evidence_chunks",
            "evidence_chunks",
            ["parent_id"],
            ["id"],
            ondelete="SET NULL",
        )
    existing_indexes = {index["name"] for index in inspector.get_indexes("evidence_chunks")}
    for name, column in (
        ("ix_evidence_chunks_chunk_type", "chunk_type"),
        ("ix_evidence_chunks_parent_id", "parent_id"),
        ("ix_evidence_chunks_content_hash", "content_hash"),
    ):
        if name not in existing_indexes:
            op.create_index(name, "evidence_chunks", [column])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    existing_indexes = {index["name"] for index in inspector.get_indexes("evidence_chunks")}
    for index in (
        "ix_evidence_chunks_content_hash",
        "ix_evidence_chunks_parent_id",
        "ix_evidence_chunks_chunk_type",
    ):
        if index in existing_indexes:
            op.drop_index(index, table_name="evidence_chunks")
    for foreign_key in inspector.get_foreign_keys("evidence_chunks"):
        if foreign_key.get("constrained_columns") == ["parent_id"] and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], "evidence_chunks", type_="foreignkey")
            break
    existing_columns = {column["name"] for column in inspector.get_columns("evidence_chunks")}
    for column in (
        "extraction_metadata",
        "content_hash",
        "parser_version",
        "source_checksum",
        "table_reference",
        "page_number",
        "parent_id",
        "chunk_type",
    ):
        if column in existing_columns:
            op.drop_column("evidence_chunks", column)
