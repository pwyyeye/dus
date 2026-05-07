"""Initial migration

Revision ID: ab77a4968437
Revises:
Create Date: 2026-04-21 11:04:08.966386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab77a4968437'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'machines',
        sa.Column('id', sa.CHAR(32), primary_key=True),
        sa.Column('machine_id', sa.String(255), unique=True, nullable=False),
        sa.Column('machine_name', sa.String(255), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('agent_capability', sa.String(20), nullable=False),
        sa.Column('agent_version', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='offline'),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('agent_status', sa.String(20), nullable=False, server_default='offline'),
        sa.Column('last_poll_at', sa.DateTime, nullable=True),
        sa.Column('registered_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_machines_status', 'machines', ['status'])
    op.create_index('idx_machines_agent_type', 'machines', ['agent_type'])

    op.create_table(
        'projects',
        sa.Column('id', sa.CHAR(32), primary_key=True),
        sa.Column('project_id', sa.String(255), unique=True, nullable=False),
        sa.Column('project_name', sa.String(255), nullable=False),
        sa.Column('root_path', sa.String(1024), nullable=True),
        sa.Column('idle_threshold_hours', sa.Integer, nullable=False, server_default='48'),
        sa.Column('reminder_interval_hours', sa.Integer, nullable=False, server_default='24'),
        sa.Column('last_activity_at', sa.DateTime, nullable=True),
        sa.Column('is_archived', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'tasks',
        sa.Column('id', sa.CHAR(32), primary_key=True),
        sa.Column('task_id', sa.String(255), unique=True, nullable=False),
        sa.Column('instruction', sa.Text, nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('project_id', sa.CHAR(32), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('target_machine_id', sa.CHAR(32), sa.ForeignKey('machines.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('result', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text, nullable=True),
    )
    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_target', 'tasks', ['target_machine_id'])
    op.create_index('idx_tasks_project', 'tasks', ['project_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('tasks')
    op.drop_table('projects')
    op.drop_table('machines')
