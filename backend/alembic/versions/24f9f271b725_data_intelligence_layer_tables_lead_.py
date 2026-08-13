"""data intelligence layer tables + lead quality columns

Revision ID: 24f9f271b725
Revises: be3f7a21c909
Create Date: 2026-08-13 19:53:16.545791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24f9f271b725'
down_revision: Union[str, None] = 'be3f7a21c909'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- entities + provenance ---
    op.create_table('sources',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_type', sa.String(length=40), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('access_status', sa.String(length=20), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url', name='uq_sources_url'),
    )
    op.create_index(op.f('ix_sources_source_type'), 'sources', ['source_type'], unique=False)
    op.create_index(op.f('ix_sources_domain'), 'sources', ['domain'], unique=False)

    op.create_table('source_evidence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('field_name', sa.String(length=60), nullable=False),
        sa.Column('field_value', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(length=40), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', 'field_name', 'field_value', name='uq_evidence_field'),
    )
    op.create_index(op.f('ix_source_evidence_source_id'), 'source_evidence', ['source_id'], unique=False)
    op.create_index(op.f('ix_source_evidence_entity_type'), 'source_evidence', ['entity_type'], unique=False)
    op.create_index(op.f('ix_source_evidence_entity_id'), 'source_evidence', ['entity_id'], unique=False)
    op.create_index(op.f('ix_source_evidence_field_name'), 'source_evidence', ['field_name'], unique=False)

    op.create_table('emails',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('value', sa.String(length=320), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('classification', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('verification_meta', sa.JSON(), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('value', name='uq_emails_value'),
    )
    op.create_index(op.f('ix_emails_value'), 'emails', ['value'], unique=False)
    op.create_index(op.f('ix_emails_entity_id'), 'emails', ['entity_id'], unique=False)
    op.create_index(op.f('ix_emails_classification'), 'emails', ['classification'], unique=False)
    op.create_index(op.f('ix_emails_status'), 'emails', ['status'], unique=False)

    op.create_table('phones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('raw_phone', sa.String(length=60), nullable=False),
        sa.Column('e164', sa.String(length=20), nullable=True),
        sa.Column('country_code', sa.String(length=2), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('normalization', sa.String(length=20), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('e164', name='uq_phones_e164'),
    )
    op.create_index(op.f('ix_phones_e164'), 'phones', ['e164'], unique=False)
    op.create_index(op.f('ix_phones_entity_id'), 'phones', ['entity_id'], unique=False)

    op.create_table('social_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('platform', sa.String(length=30), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'url', name='uq_social_platform_url'),
    )
    op.create_index(op.f('ix_social_profiles_platform'), 'social_profiles', ['platform'], unique=False)
    op.create_index(op.f('ix_social_profiles_entity_id'), 'social_profiles', ['entity_id'], unique=False)

    op.create_table('people',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=120), nullable=True),
        sa.Column('last_name', sa.String(length=120), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('department', sa.String(length=255), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('profile_url', sa.String(length=1000), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('full_name', 'profile_url', name='uq_people_name_url'),
    )
    op.create_index(op.f('ix_people_full_name'), 'people', ['full_name'], unique=False)
    op.create_index(op.f('ix_people_title'), 'people', ['title'], unique=False)

    op.create_table('company_people',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('person_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=255), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], ),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'person_id', name='uq_company_person'),
    )
    op.create_index(op.f('ix_company_people_company_id'), 'company_people', ['company_id'], unique=False)
    op.create_index(op.f('ix_company_people_person_id'), 'company_people', ['person_id'], unique=False)

    # --- crawl frontier ---
    op.create_table('crawl_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('search_id', sa.String(length=36), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_pages', sa.Integer(), nullable=False),
        sa.Column('pages_crawled', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(length=1000), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_crawl_jobs_search_id'), 'crawl_jobs', ['search_id'], unique=False)
    op.create_index(op.f('ix_crawl_jobs_entity_id'), 'crawl_jobs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_crawl_jobs_status'), 'crawl_jobs', ['status'], unique=False)

    op.create_table('crawl_pages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('crawl_job_id', sa.String(length=36), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('canonical_url', sa.String(length=1000), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('depth', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(length=1000), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('crawled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['crawl_job_id'], ['crawl_jobs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('crawl_job_id', 'url', name='uq_crawl_page_url'),
    )
    op.create_index(op.f('ix_crawl_pages_crawl_job_id'), 'crawl_pages', ['crawl_job_id'], unique=False)
    op.create_index(op.f('ix_crawl_pages_domain'), 'crawl_pages', ['domain'], unique=False)
    op.create_index(op.f('ix_crawl_pages_priority'), 'crawl_pages', ['priority'], unique=False)
    op.create_index(op.f('ix_crawl_pages_status'), 'crawl_pages', ['status'], unique=False)

    # --- runs + verification ---
    op.create_table('enrichment_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('items_found', sa.JSON(), nullable=True),
        sa.Column('last_error', sa.String(length=1000), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_enrichment_runs_lead_id'), 'enrichment_runs', ['lead_id'], unique=False)
    op.create_index(op.f('ix_enrichment_runs_entity_id'), 'enrichment_runs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_enrichment_runs_status'), 'enrichment_runs', ['status'], unique=False)

    op.create_table('verification_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('field_name', sa.String(length=30), nullable=False),
        sa.Column('field_value', sa.Text(), nullable=False),
        sa.Column('result', sa.String(length=20), nullable=False),
        sa.Column('checks', sa.JSON(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_verification_results_entity_id'), 'verification_results', ['entity_id'], unique=False)
    op.create_index(op.f('ix_verification_results_field_name'), 'verification_results', ['field_name'], unique=False)
    op.create_index(op.f('ix_verification_results_result'), 'verification_results', ['result'], unique=False)

    # --- resolution + quality + history ---
    op.create_table('entity_matches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('primary_id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=36), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=False),
        sa.Column('method', sa.String(length=20), nullable=False),
        sa.Column('detail', sa.String(length=500), nullable=True),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'primary_id', 'candidate_id', name='uq_entity_match_pair'),
    )
    op.create_index(op.f('ix_entity_matches_entity_type'), 'entity_matches', ['entity_type'], unique=False)
    op.create_index(op.f('ix_entity_matches_primary_id'), 'entity_matches', ['primary_id'], unique=False)
    op.create_index(op.f('ix_entity_matches_candidate_id'), 'entity_matches', ['candidate_id'], unique=False)

    op.create_table('data_quality_scores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('field_name', sa.String(length=60), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('source_count', sa.Integer(), nullable=False),
        sa.Column('last_computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', 'field_name', name='uq_quality_field'),
    )
    op.create_index(op.f('ix_data_quality_scores_entity_id'), 'data_quality_scores', ['entity_id'], unique=False)
    op.create_index(op.f('ix_data_quality_scores_field_name'), 'data_quality_scores', ['field_name'], unique=False)

    op.create_table('field_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('field_name', sa.String(length=60), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_field_history_entity_type'), 'field_history', ['entity_type'], unique=False)
    op.create_index(op.f('ix_field_history_entity_id'), 'field_history', ['entity_id'], unique=False)
    op.create_index(op.f('ix_field_history_field_name'), 'field_history', ['field_name'], unique=False)

    op.create_table('technographics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('technology', sa.String(length=120), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'technology', name='uq_technographic'),
    )
    op.create_index(op.f('ix_technographics_company_id'), 'technographics', ['company_id'], unique=False)

    op.create_table('intent_signals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('signal', sa.String(length=120), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_intent_signals_lead_id'), 'intent_signals', ['lead_id'], unique=False)
    op.create_index(op.f('ix_intent_signals_entity_id'), 'intent_signals', ['entity_id'], unique=False)
    op.create_index(op.f('ix_intent_signals_signal'), 'intent_signals', ['signal'], unique=False)

    op.create_table('verified_flags',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('flag', sa.String(length=40), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_verified_flags_entity_type'), 'verified_flags', ['entity_type'], unique=False)
    op.create_index(op.f('ix_verified_flags_entity_id'), 'verified_flags', ['entity_id'], unique=False)
    op.create_index(op.f('ix_verified_flags_flag'), 'verified_flags', ['flag'], unique=False)

    # --- additive lead quality/provenance columns ---
    op.add_column('leads', sa.Column('company_id', sa.String(length=36), nullable=True))
    op.add_column('leads', sa.Column('person_id', sa.String(length=36), nullable=True))
    op.add_column('leads', sa.Column('overall_quality_score', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('freshness_score', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('source_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_leads_company_id'), 'leads', ['company_id'], unique=False)
    op.create_index(op.f('ix_leads_person_id'), 'leads', ['person_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leads_person_id'), table_name='leads')
    op.drop_index(op.f('ix_leads_company_id'), table_name='leads')
    op.drop_column('leads', 'content_hash')
    op.drop_column('leads', 'source_count')
    op.drop_column('leads', 'last_verified_at')
    op.drop_column('leads', 'freshness_score')
    op.drop_column('leads', 'overall_quality_score')
    op.drop_column('leads', 'person_id')
    op.drop_column('leads', 'company_id')

    op.drop_index(op.f('ix_verified_flags_flag'), table_name='verified_flags')
    op.drop_index(op.f('ix_verified_flags_entity_id'), table_name='verified_flags')
    op.drop_index(op.f('ix_verified_flags_entity_type'), table_name='verified_flags')
    op.drop_table('verified_flags')

    op.drop_index(op.f('ix_intent_signals_signal'), table_name='intent_signals')
    op.drop_index(op.f('ix_intent_signals_entity_id'), table_name='intent_signals')
    op.drop_index(op.f('ix_intent_signals_lead_id'), table_name='intent_signals')
    op.drop_table('intent_signals')

    op.drop_index(op.f('ix_technographics_company_id'), table_name='technographics')
    op.drop_table('technographics')

    op.drop_index(op.f('ix_field_history_field_name'), table_name='field_history')
    op.drop_index(op.f('ix_field_history_entity_id'), table_name='field_history')
    op.drop_index(op.f('ix_field_history_entity_type'), table_name='field_history')
    op.drop_table('field_history')

    op.drop_index(op.f('ix_data_quality_scores_field_name'), table_name='data_quality_scores')
    op.drop_index(op.f('ix_data_quality_scores_entity_id'), table_name='data_quality_scores')
    op.drop_table('data_quality_scores')

    op.drop_index(op.f('ix_entity_matches_candidate_id'), table_name='entity_matches')
    op.drop_index(op.f('ix_entity_matches_primary_id'), table_name='entity_matches')
    op.drop_index(op.f('ix_entity_matches_entity_type'), table_name='entity_matches')
    op.drop_table('entity_matches')

    op.drop_index(op.f('ix_verification_results_result'), table_name='verification_results')
    op.drop_index(op.f('ix_verification_results_field_name'), table_name='verification_results')
    op.drop_index(op.f('ix_verification_results_entity_id'), table_name='verification_results')
    op.drop_table('verification_results')

    op.drop_index(op.f('ix_enrichment_runs_status'), table_name='enrichment_runs')
    op.drop_index(op.f('ix_enrichment_runs_entity_id'), table_name='enrichment_runs')
    op.drop_index(op.f('ix_enrichment_runs_lead_id'), table_name='enrichment_runs')
    op.drop_table('enrichment_runs')

    op.drop_index(op.f('ix_crawl_pages_status'), table_name='crawl_pages')
    op.drop_index(op.f('ix_crawl_pages_priority'), table_name='crawl_pages')
    op.drop_index(op.f('ix_crawl_pages_domain'), table_name='crawl_pages')
    op.drop_index(op.f('ix_crawl_pages_crawl_job_id'), table_name='crawl_pages')
    op.drop_table('crawl_pages')

    op.drop_index(op.f('ix_crawl_jobs_status'), table_name='crawl_jobs')
    op.drop_index(op.f('ix_crawl_jobs_entity_id'), table_name='crawl_jobs')
    op.drop_index(op.f('ix_crawl_jobs_search_id'), table_name='crawl_jobs')
    op.drop_table('crawl_jobs')

    op.drop_index(op.f('ix_company_people_person_id'), table_name='company_people')
    op.drop_index(op.f('ix_company_people_company_id'), table_name='company_people')
    op.drop_table('company_people')

    op.drop_index(op.f('ix_people_title'), table_name='people')
    op.drop_index(op.f('ix_people_full_name'), table_name='people')
    op.drop_table('people')

    op.drop_index(op.f('ix_social_profiles_entity_id'), table_name='social_profiles')
    op.drop_index(op.f('ix_social_profiles_platform'), table_name='social_profiles')
    op.drop_table('social_profiles')

    op.drop_index(op.f('ix_phones_entity_id'), table_name='phones')
    op.drop_index(op.f('ix_phones_e164'), table_name='phones')
    op.drop_table('phones')

    op.drop_index(op.f('ix_emails_status'), table_name='emails')
    op.drop_index(op.f('ix_emails_classification'), table_name='emails')
    op.drop_index(op.f('ix_emails_entity_id'), table_name='emails')
    op.drop_index(op.f('ix_emails_value'), table_name='emails')
    op.drop_table('emails')

    op.drop_index(op.f('ix_source_evidence_field_name'), table_name='source_evidence')
    op.drop_index(op.f('ix_source_evidence_entity_id'), table_name='source_evidence')
    op.drop_index(op.f('ix_source_evidence_entity_type'), table_name='source_evidence')
    op.drop_index(op.f('ix_source_evidence_source_id'), table_name='source_evidence')
    op.drop_table('source_evidence')

    op.drop_index(op.f('ix_sources_domain'), table_name='sources')
    op.drop_index(op.f('ix_sources_source_type'), table_name='sources')
    op.drop_table('sources')