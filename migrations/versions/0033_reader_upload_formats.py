"""Use case: Lets uploads record reader-based stored formats such as "r:sas7bdat".

What it does: Widens uploads.format from 5 to 16 characters; downgrade refuses while any
upload uses a longer format code.
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("uploads", "format", type_=sa.String(16), existing_nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM uploads WHERE length(format) > 5 LIMIT 1")).first():
        raise RuntimeError("Uploads with reader-based formats exist; refusing to discard them.")
    op.alter_column("uploads", "format", type_=sa.String(5), existing_nullable=False)
