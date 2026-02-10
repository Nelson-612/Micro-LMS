"""add grading fields to submissions

Revision ID: de570aa59e05
Revises: 4a3633d810ed
Create Date: 2026-02-09 23:49:20.694049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de570aa59e05'
down_revision: Union[str, Sequence[str], None] = '4a3633d810ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    rows = bind.exec_driver_sql("PRAGMA table_info(submissions);").fetchall()
    existing_cols = {r[1] for r in rows}

    if "score" not in existing_cols:
        op.add_column("submissions", sa.Column("score", sa.Integer(), nullable=True))
    if "feedback" not in existing_cols:
        op.add_column("submissions", sa.Column("feedback", sa.Text(), nullable=True))
    if "graded_at" not in existing_cols:
        op.add_column("submissions", sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    pass