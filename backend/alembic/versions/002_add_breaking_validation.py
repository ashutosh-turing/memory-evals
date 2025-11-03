"""Add threshold-based breaking validation

Revision ID: 002_add_breaking_validation
Revises: 001_initial_schema
Create Date: 2025-11-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_breaking_validation'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add threshold and breaking analysis columns."""
    # Add threshold configuration to tasks table
    op.add_column('tasks', sa.Column('rubric_thresholds', sa.JSON(), nullable=True))
    
    # Add breaking analysis columns to scores table
    op.add_column('scores', sa.Column('breaking_dimensions', sa.JSON(), nullable=True))
    op.add_column('scores', sa.Column('breaking_details', sa.JSON(), nullable=True))
    op.add_column('scores', sa.Column('thresholds_used', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove threshold and breaking analysis columns."""
    # Remove from scores table
    op.drop_column('scores', 'thresholds_used')
    op.drop_column('scores', 'breaking_details')
    op.drop_column('scores', 'breaking_dimensions')
    
    # Remove from tasks table
    op.drop_column('tasks', 'rubric_thresholds')

