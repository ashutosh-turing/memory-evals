"""Initial schema - Create all tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with complete schema."""
    
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pr_url', sa.String(length=512), nullable=False),
        sa.Column('repo', sa.String(length=256), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('max_files', sa.Integer(), nullable=False),
        
        # User context fields (for multi-tenancy)
        sa.Column('created_by_user_id', sa.String(length=255), nullable=True),
        sa.Column('created_by_email', sa.String(length=255), nullable=True),
        sa.Column('created_by_name', sa.String(length=255), nullable=True),
        sa.Column('org_id', sa.String(length=255), nullable=True),
        sa.Column('team_id', sa.String(length=255), nullable=True),
        sa.Column('project_id', sa.String(length=255), nullable=True),
        
        # JSON fields
        sa.Column('agents', sa.JSON(), nullable=True),
        sa.Column('rubric', sa.JSON(), nullable=True),
        sa.Column('changed_files', sa.JSON(), nullable=True),
        
        # Metadata
        sa.Column('prompt_hash', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for tasks table
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_created_by_user_id', 'tasks', ['created_by_user_id'])
    op.create_index('ix_tasks_team_id', 'tasks', ['team_id'])
    op.create_index('ix_tasks_org_id', 'tasks', ['org_id'])
    op.create_index('ix_tasks_created_at', 'tasks', ['created_at'])
    
    # Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        
        # JSON fields
        sa.Column('milestones', sa.JSON(), nullable=True),
        sa.Column('artifacts', sa.JSON(), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=True),
        
        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for agent_runs table
    op.create_index('ix_agent_runs_task_id', 'agent_runs', ['task_id'])
    op.create_index('ix_agent_runs_status', 'agent_runs', ['status'])
    op.create_index('ix_agent_runs_agent', 'agent_runs', ['agent'])
    
    # Create scores table
    op.create_table(
        'scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent', sa.String(length=50), nullable=False),
        
        # Scoring
        sa.Column('scores', sa.JSON(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        
        # Judge information
        sa.Column('judge_type', sa.String(length=50), nullable=False),
        sa.Column('judge_model', sa.String(length=100), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        
        # A/B comparison data
        sa.Column('pre_compression_answers', sa.JSON(), nullable=True),
        sa.Column('post_compression_answers', sa.JSON(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for scores table
    op.create_index('ix_scores_agent_run_id', 'scores', ['agent_run_id'])
    op.create_index('ix_scores_task_id', 'scores', ['task_id'])
    op.create_index('ix_scores_agent', 'scores', ['agent'])
    
    # Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent', sa.String(length=50), nullable=False),
        
        # File information
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=1024), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for artifacts table
    op.create_index('ix_artifacts_agent_run_id', 'artifacts', ['agent_run_id'])
    op.create_index('ix_artifacts_task_id', 'artifacts', ['task_id'])
    op.create_index('ix_artifacts_file_type', 'artifacts', ['file_type'])


def downgrade() -> None:
    """Drop all tables."""
    # Drop tables in reverse order
    op.drop_index('ix_artifacts_file_type', table_name='artifacts')
    op.drop_index('ix_artifacts_task_id', table_name='artifacts')
    op.drop_index('ix_artifacts_agent_run_id', table_name='artifacts')
    op.drop_table('artifacts')
    
    op.drop_index('ix_scores_agent', table_name='scores')
    op.drop_index('ix_scores_task_id', table_name='scores')
    op.drop_index('ix_scores_agent_run_id', table_name='scores')
    op.drop_table('scores')
    
    op.drop_index('ix_agent_runs_agent', table_name='agent_runs')
    op.drop_index('ix_agent_runs_status', table_name='agent_runs')
    op.drop_index('ix_agent_runs_task_id', table_name='agent_runs')
    op.drop_table('agent_runs')
    
    op.drop_index('ix_tasks_created_at', table_name='tasks')
    op.drop_index('ix_tasks_org_id', table_name='tasks')
    op.drop_index('ix_tasks_team_id', table_name='tasks')
    op.drop_index('ix_tasks_created_by_user_id', table_name='tasks')
    op.drop_index('ix_tasks_status', table_name='tasks')
    op.drop_table('tasks')

