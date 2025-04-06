"""Add patient_id to Transcription

Revision ID: a9ffabe7eba5
Revises: 3bc4a120f88a
Create Date: 2025-04-06 20:36:46.006167

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9ffabe7eba5'
down_revision = '3bc4a120f88a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('patient_id', sa.String(length=50), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.drop_column('patient_id')

    # ### end Alembic commands ###
