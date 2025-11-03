"""Add qa_interactions column to agent_runs

Revision ID: 003_add_qa_interactions
Revises: 002_add_breaking_validation
Create Date: 2025-11-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_qa_interactions'
down_revision = '002_add_breaking_validation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add qa_interactions column to agent_runs table."""
    op.add_column('agent_runs', sa.Column('qa_interactions', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove qa_interactions column from agent_runs table."""
    op.drop_column('agent_runs', 'qa_interactions')

