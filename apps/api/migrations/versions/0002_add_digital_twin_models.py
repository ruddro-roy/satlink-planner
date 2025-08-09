"""Add Digital Twin models

Revision ID: 0002
Revises: 0001
Create Date: 2025-08-09 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    # Create new enum types
    tle_source = sa.Enum('space_track', 'celestrak', 'manual', 'other', name='tlesource')
    tle_accuracy = sa.Enum('high', 'medium', 'low', name='tleaccuracy')
    cola_status = sa.Enum('pending', 'in_progress', 'completed', 'failed', name='colastatus')
    node_type = sa.Enum('satellite', 'ground_station', 'gateway', 'relay', 'user_terminal', name='nodetype')
    anomaly_type = sa.Enum('tle_aging', 'collision_risk', 'link_margin', 'system_health', 'data_quality', 'operational', name='anomalytype')
    anomaly_severity = sa.Enum('info', 'warning', 'critical', name='anomalyseverity')
    anomaly_status = sa.Enum('detected', 'acknowledged', 'resolved', 'false_positive', name='anomalystatus')
    
    # Create all enums first
    tle_source.create(op.get_bind())
    tle_accuracy.create(op.get_bind())
    cola_status.create(op.get_bind())
    node_type.create(op.get_bind())
    anomaly_type.create(op.get_bind())
    anomaly_severity.create(op.get_bind())
    anomaly_status.create(op.get_bind())
    
    # Create new tables
    op.create_table('tle_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('satellite_id', sa.Integer(), nullable=False),
        sa.Column('tle_line1', sa.String(), nullable=False),
        sa.Column('tle_line2', sa.String(), nullable=False),
        sa.Column('tle_epoch', sa.DateTime(), nullable=False),
        sa.Column('source', tle_accuracy, nullable=False, server_default='manual'),
        sa.Column('accuracy', tle_accuracy, nullable=True),
        sa.Column('position_error_km', sa.Float(), nullable=True),
        sa.Column('is_current', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['satellite_id'], ['satellites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tle_satellite_epoch', 'tle_history', ['satellite_id', 'tle_epoch'], unique=True)
    
    op.create_table('collision_risk_assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('satellite_id', sa.Integer(), nullable=False),
        sa.Column('assessment_time', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('assessment_window_hours', sa.Integer(), server_default='72', nullable=False),
        sa.Column('status', cola_status, server_default='pending', nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('closest_approach_km', sa.Float(), nullable=True),
        sa.Column('closest_approach_time', sa.DateTime(), nullable=True),
        sa.Column('objects_at_risk', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['satellite_id'], ['satellites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('frequency_allocations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('satellite_id', sa.Integer(), nullable=False),
        sa.Column('frequency_mhz', sa.Float(), nullable=False),
        sa.Column('bandwidth_mhz', sa.Float(), nullable=False),
        sa.Column('service', sa.String(), nullable=True),
        sa.Column('itu_region', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('coordination_notes', sa.Text(), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['satellite_id'], ['satellites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_freq_alloc_satellite_band', 'frequency_allocations', 
                   ['satellite_id', 'frequency_mhz', 'bandwidth_mhz'], unique=False)
    
    op.create_table('network_nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('node_type', node_type, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('node_id')
    )
    
    op.create_table('network_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_node_id', sa.Integer(), nullable=False),
        sa.Column('target_node_id', sa.Integer(), nullable=False),
        sa.Column('link_type', sa.String(), nullable=True),
        sa.Column('frequency_mhz', sa.Float(), nullable=True),
        sa.Column('bandwidth_mhz', sa.Float(), nullable=True),
        sa.Column('max_data_rate_mbps', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_node_id'], ['network_nodes.id'], ),
        sa.ForeignKeyConstraint(['target_node_id'], ['network_nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_network_link_nodes', 'network_links', ['source_node_id', 'target_node_id'], unique=False)
    
    op.create_table('handover_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('link_id', sa.Integer(), nullable=False),
        sa.Column('satellite_id', sa.Integer(), nullable=False),
        sa.Column('ground_station_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(), server_default='scheduled', nullable=False),
        sa.Column('handover_type', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['ground_station_id'], ['ground_stations.id'], ),
        sa.ForeignKeyConstraint(['link_id'], ['network_links.id'], ),
        sa.ForeignKeyConstraint(['satellite_id'], ['satellites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_handover_times', 'handover_schedules', ['start_time', 'end_time'], unique=False)
    op.create_index('idx_handover_sat_gs', 'handover_schedules', ['satellite_id', 'ground_station_id'], unique=False)
    
    op.create_table('anomaly_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('anomaly_type', anomaly_type, nullable=False),
        sa.Column('severity', anomaly_severity, nullable=False),
        sa.Column('status', anomaly_status, server_default='detected', nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('satellite_id', sa.Integer(), nullable=True),
        sa.Column('ground_station_id', sa.Integer(), nullable=True),
        sa.Column('link_id', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['ground_station_id'], ['ground_stations.id'], ),
        sa.ForeignKeyConstraint(['link_id'], ['network_links.id'], ),
        sa.ForeignKeyConstraint(['satellite_id'], ['satellites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('anomaly_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('anomaly_id', sa.Integer(), nullable=False),
        sa.Column('response_type', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('executed_by', sa.String(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['anomaly_id'], ['anomaly_detections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add columns to existing tables
    op.add_column('satellites', sa.Column('norad_id', sa.String(), nullable=True))
    op.add_column('satellites', sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))
    op.add_column('satellites', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))
    
    op.add_column('ground_stations', sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))
    op.add_column('ground_stations', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))
    
    # Create indexes
    op.create_index(op.f('ix_anomaly_detections_anomaly_type'), 'anomaly_detections', ['anomaly_type'], unique=False)
    op.create_index(op.f('ix_anomaly_detections_severity'), 'anomaly_detections', ['severity'], unique=False)
    op.create_index(op.f('ix_anomaly_detections_status'), 'anomaly_detections', ['status'], unique=False)
    op.create_index(op.f('ix_anomaly_detections_detected_at'), 'anomaly_detections', ['detected_at'], unique=False)
    
    # Set updated_at to update on row update
    op.execute("""
        CREATE OR REPLACE FUNCTION update_modified_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    for table in ['satellites', 'ground_stations', 'network_nodes', 'network_links']:
        op.execute(f"""
            DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
        """)

def downgrade():
    # Drop tables in reverse order of creation
    op.drop_table('anomaly_responses')
    op.drop_table('anomaly_detections')
    op.drop_table('handover_schedules')
    op.drop_table('network_links')
    op.drop_table('network_nodes')
    op.drop_table('frequency_allocations')
    op.drop_table('collision_risk_assessments')
    op.drop_table('tle_history')
    
    # Drop enums
    sa.Enum(name='anomalystatus').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='anomalyseverity').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='anomalytype').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='nodetype').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='colastatus').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='tleaccuracy').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='tlesource').drop(op.get_bind(), checkfirst=False)
    
    # Drop columns from existing tables
    op.drop_column('satellites', 'norad_id')
    op.drop_column('satellites', 'created_at')
    op.drop_column('satellites', 'updated_at')
    
    op.drop_column('ground_stations', 'created_at')
    op.drop_column('ground_stations', 'updated_at')
    
    # Drop the update_modified_column function
    op.execute("DROP FUNCTION IF EXISTS update_modified_column();")
