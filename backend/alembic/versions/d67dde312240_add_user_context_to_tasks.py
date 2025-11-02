"""add_user_context_to_tasks

Revision ID: d67dde312240
Revises: 46022896a035
Create Date: 2025-11-02 19:11:39.994212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd67dde312240'
down_revision: Union[str, Sequence[str], None] = '46022896a035'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add user context fields to tasks table."""
    # Add user context columns (nullable for backward compatibility)
    op.add_column('tasks', sa.Column('created_by_user_id', sa.String(length=255), nullable=True))
    op.add_column('tasks', sa.Column('created_by_email', sa.String(length=255), nullable=True))
    op.add_column('tasks', sa.Column('created_by_name', sa.String(length=255), nullable=True))
    op.add_column('tasks', sa.Column('org_id', sa.String(length=255), nullable=True))
    op.add_column('tasks', sa.Column('team_id', sa.String(length=255), nullable=True))
    op.add_column('tasks', sa.Column('project_id', sa.String(length=255), nullable=True))
    
    # Create indexes for efficient filtering by user and team
    op.create_index('ix_tasks_created_by_user_id', 'tasks', ['created_by_user_id'])
    op.create_index('ix_tasks_team_id', 'tasks', ['team_id'])
    op.create_index('ix_tasks_org_id', 'tasks', ['org_id'])


def downgrade() -> None:
    """Downgrade schema - Remove user context fields from tasks table."""
    # Drop indexes first
    op.drop_index('ix_tasks_org_id', table_name='tasks')
    op.drop_index('ix_tasks_team_id', table_name='tasks')
    op.drop_index('ix_tasks_created_by_user_id', table_name='tasks')
    
    # Drop columns
    op.drop_column('tasks', 'project_id')
    op.drop_column('tasks', 'team_id')
    op.drop_column('tasks', 'org_id')
    op.drop_column('tasks', 'created_by_name')
    op.drop_column('tasks', 'created_by_email')
    op.drop_column('tasks', 'created_by_user_id')
