"""merge heads before billing

Revision ID: 40bd68fa6124
Revises: 17ed7d600883, be3f7a21c909
Create Date: 2026-08-27 14:01:06.274717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40bd68fa6124'
down_revision: Union[str, None] = ('17ed7d600883', 'be3f7a21c909')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
