"""add unique constraint submission assignment student

Revision ID: 4a3633d810ed
Revises: a5b9f3826e46
Create Date: 2026-02-09 23:08:57.548406

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4a3633d810ed'
down_revision: Union[str, Sequence[str], None] = 'a5b9f3826e46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("submissions", recreate="always") as batch_op:
        batch_op.create_unique_constraint(
            "uq_submission_assignment_student",
            ["assignment_id", "student_id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("submissions", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "uq_submission_assignment_student",
            type_="unique",
        )