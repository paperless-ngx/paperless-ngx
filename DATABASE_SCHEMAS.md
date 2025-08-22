# Schémas de Base de Données - Extension Paperless-ngx

## Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Modèles IA Engine](#modèles-ia-engine)
3. [Modèles OCR Hybride](#modèles-ocr-hybride)
4. [Modèles Calendrier](#modèles-calendrier)
5. [Modèles Mail IA](#modèles-mail-ia)
6. [Extensions des modèles existants](#extensions-des-modèles-existants)
7. [Index et contraintes](#index-et-contraintes)
8. [Migrations](#migrations)
9. [Vues et fonctions](#vues-et-fonctions)

## Vue d'ensemble

Les nouveaux schémas étendent la base de données Paperless-ngx existante en ajoutant des tables spécialisées pour les fonctionnalités IA tout en maintenant l'intégrité référentielle avec les modèles existants.

### Conventions de nommage
- **Tables** : `{app_name}_{model_name}` (ex: `paperless_ai_engine_documentembedding`)
- **Index** : `idx_{table}_{columns}` (ex: `idx_document_embedding_model`)
- **Contraintes** : `{table}_{constraint_type}_{columns}` (ex: `document_embedding_unique_document`)

### Types de données
- **PostgreSQL** : Types natifs avec JSON/JSONB pour structures complexes
- **SQLite** : Adaptation avec TEXT pour JSON, REAL pour float
- **MariaDB** : Types standards avec JSON pour structures complexes

## Modèles IA Engine

### 1. Configuration IA Globale

```sql
-- paperless_ai_engine_aiconfiguration
CREATE TABLE paperless_ai_engine_aiconfiguration (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL DEFAULT 'default',

    -- Configuration modèle d'embedding
    embedding_model VARCHAR(256) NOT NULL DEFAULT 'distilbert-base-multilingual-cased',
    embedding_dimension INTEGER NOT NULL DEFAULT 768,
    embedding_batch_size INTEGER NOT NULL DEFAULT 16,
    embedding_cache_enabled BOOLEAN NOT NULL DEFAULT true,

    -- Configuration LLM
    llm_model_path VARCHAR(512),
    llm_max_tokens INTEGER DEFAULT 2048,
    llm_temperature DECIMAL(3,2) DEFAULT 0.10,
    llm_gpu_enabled BOOLEAN DEFAULT false,

    -- Configuration recherche
    search_similarity_threshold DECIMAL(3,2) DEFAULT 0.70,
    search_max_results INTEGER DEFAULT 50,
    search_reranking_enabled BOOLEAN DEFAULT true,

    -- Limites de ressources
    max_memory_mb INTEGER DEFAULT 4096,
    max_concurrent_tasks INTEGER DEFAULT 4,
    task_timeout_seconds INTEGER DEFAULT 300,

    -- Fonctionnalités activées (JSON array)
    enabled_features JSON NOT NULL DEFAULT '["semantic_search"]',

    -- Métadonnées
    is_active BOOLEAN NOT NULL DEFAULT false,
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT aiconfiguration_name_unique UNIQUE (name),
    CONSTRAINT aiconfiguration_embedding_dimension_positive CHECK (embedding_dimension > 0),
    CONSTRAINT aiconfiguration_batch_size_positive CHECK (embedding_batch_size > 0),
    CONSTRAINT aiconfiguration_threshold_range CHECK (search_similarity_threshold >= 0 AND search_similarity_threshold <= 1),
    CONSTRAINT aiconfiguration_temperature_range CHECK (llm_temperature >= 0 AND llm_temperature <= 2)
);
```

### 2. Embeddings de Documents

```sql
-- paperless_ai_engine_documentembedding
CREATE TABLE paperless_ai_engine_documentembedding (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents_document(id) ON DELETE CASCADE,

    -- Vecteur d'embedding (JSON array of floats)
    embedding_vector JSON NOT NULL,
    embedding_dimension INTEGER NOT NULL,

    -- Métadonnées du modèle
    model_name VARCHAR(256) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    model_hash VARCHAR(64), -- Hash pour détecter les changements de modèle

    -- Métriques de qualité
    confidence_score DECIMAL(5,4),
    processing_time DECIMAL(8,3), -- en secondes
    chunk_index INTEGER DEFAULT 0, -- pour documents en plusieurs chunks
    total_chunks INTEGER DEFAULT 1,

    -- Métadonnées du document au moment de l'embedding
    document_content_hash VARCHAR(64) NOT NULL, -- Pour détecter les changements
    document_page_count INTEGER,
    document_word_count INTEGER,

    -- Timestamps
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT document_embedding_unique_document_chunk UNIQUE (document_id, chunk_index),
    CONSTRAINT document_embedding_dimension_positive CHECK (embedding_dimension > 0),
    CONSTRAINT document_embedding_confidence_range CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    CONSTRAINT document_embedding_chunk_valid CHECK (chunk_index >= 0 AND chunk_index < total_chunks)
);
```

### 3. Requêtes Sémantiques

```sql
-- paperless_ai_engine_semanticquery
CREATE TABLE paperless_ai_engine_semanticquery (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,

    -- Requête
    query_text TEXT NOT NULL,
    query_embedding JSON NOT NULL,
    query_language VARCHAR(8) DEFAULT 'auto',

    -- Paramètres de recherche
    similarity_threshold DECIMAL(3,2) NOT NULL,
    max_results INTEGER NOT NULL,
    filters JSON, -- Filtres appliqués (types, tags, etc.)

    -- Résultats
    results_count INTEGER NOT NULL DEFAULT 0,
    results_document_ids JSON, -- Array des IDs de documents trouvés

    -- Métriques de performance
    embedding_time DECIMAL(8,3), -- Temps de génération embedding
    search_time DECIMAL(8,3), -- Temps de recherche vectorielle
    total_time DECIMAL(8,3), -- Temps total

    -- Métadonnées
    ip_address INET,
    user_agent TEXT,
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT semantic_query_threshold_range CHECK (similarity_threshold >= 0 AND similarity_threshold <= 1),
    CONSTRAINT semantic_query_max_results_positive CHECK (max_results > 0),
    CONSTRAINT semantic_query_results_count_positive CHECK (results_count >= 0)
);
```

### 4. Résultats d'Analyse IA

```sql
-- paperless_ai_engine_aianalysisresult
CREATE TABLE paperless_ai_engine_aianalysisresult (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents_document(id) ON DELETE CASCADE,

    -- Type d'analyse
    analysis_type VARCHAR(64) NOT NULL, -- 'classification', 'entity_extraction', 'summarization'

    -- Résultats (structure JSON flexible)
    results JSON NOT NULL,

    -- Métriques
    confidence_score DECIMAL(5,4),
    processing_time DECIMAL(8,3),
    model_name VARCHAR(256),
    model_version VARCHAR(64),

    -- Statut
    status VARCHAR(32) NOT NULL DEFAULT 'completed', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,

    -- Métadonnées
    triggered_by_user_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT ai_analysis_result_confidence_range CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    CONSTRAINT ai_analysis_result_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);
```

## Modèles OCR Hybride

### 1. Configuration OCR

```sql
-- paperless_ai_ocr_ocrconfiguration
CREATE TABLE paperless_ai_ocr_ocrconfiguration (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,

    -- Moteurs OCR
    primary_engine VARCHAR(64) NOT NULL DEFAULT 'tesseract',
    secondary_engine VARCHAR(64),
    fallback_engine VARCHAR(64),

    -- Stratégie de fusion
    fusion_strategy VARCHAR(64) NOT NULL DEFAULT 'confidence', -- 'confidence', 'voting', 'weighted'
    confidence_threshold DECIMAL(3,2) DEFAULT 0.80,
    voting_weight_primary DECIMAL(3,2) DEFAULT 0.60,
    voting_weight_secondary DECIMAL(3,2) DEFAULT 0.40,

    -- Préprocessing
    preprocessing_enabled BOOLEAN DEFAULT true,
    preprocessing_options JSON DEFAULT '{"deskew": true, "denoise": false, "enhance_contrast": false}',

    -- Langues supportées
    supported_languages JSON DEFAULT '["fra", "eng"]',
    auto_language_detection BOOLEAN DEFAULT true,

    -- Paramètres de performance
    parallel_processing BOOLEAN DEFAULT false,
    max_image_size_mb INTEGER DEFAULT 50,
    timeout_seconds INTEGER DEFAULT 120,

    -- Statut
    is_active BOOLEAN DEFAULT true,
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT ocr_config_name_unique UNIQUE (name),
    CONSTRAINT ocr_config_threshold_range CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    CONSTRAINT ocr_config_weights_sum CHECK (voting_weight_primary + voting_weight_secondary <= 1.0),
    CONSTRAINT ocr_config_engines_different CHECK (primary_engine != secondary_engine OR secondary_engine IS NULL)
);
```

### 2. Résultats OCR

```sql
-- paperless_ai_ocr_ocrresult
CREATE TABLE paperless_ai_ocr_ocrresult (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents_document(id) ON DELETE CASCADE,

    -- Moteur et configuration
    engine VARCHAR(64) NOT NULL,
    engine_version VARCHAR(32),
    configuration_id INTEGER REFERENCES paperless_ai_ocr_ocrconfiguration(id) ON DELETE SET NULL,

    -- Résultats texte
    extracted_text TEXT,
    text_length INTEGER,
    word_count INTEGER,
    line_count INTEGER,

    -- Métriques de qualité
    overall_confidence DECIMAL(5,4),
    avg_word_confidence DECIMAL(5,4),
    min_word_confidence DECIMAL(5,4),
    max_word_confidence DECIMAL(5,4),

    -- Bounding boxes et métadonnées spatiales
    bounding_boxes JSON, -- Array of {text, bbox, confidence, page}
    page_count INTEGER,

    -- Langues détectées
    detected_languages JSON, -- Array of {language, confidence}
    primary_language VARCHAR(8),

    -- Métriques de performance
    processing_time DECIMAL(8,3),
    preprocessing_time DECIMAL(8,3),
    ocr_time DECIMAL(8,3),
    postprocessing_time DECIMAL(8,3),

    -- Statut et erreurs
    status VARCHAR(32) NOT NULL DEFAULT 'completed',
    error_code VARCHAR(32),
    error_message TEXT,

    -- Métadonnées
    image_dpi INTEGER,
    image_format VARCHAR(16),
    image_size_mb DECIMAL(8,3),
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT ocr_result_confidence_range CHECK (
        overall_confidence IS NULL OR (overall_confidence >= 0 AND overall_confidence <= 1)
    ),
    CONSTRAINT ocr_result_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT ocr_result_counts_positive CHECK (
        text_length >= 0 AND word_count >= 0 AND line_count >= 0 AND page_count > 0
    )
);
```

### 3. Fusion OCR

```sql
-- paperless_ai_ocr_ocrfusion
CREATE TABLE paperless_ai_ocr_ocrfusion (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents_document(id) ON DELETE CASCADE,

    -- Résultats sources
    primary_result_id INTEGER REFERENCES paperless_ai_ocr_ocrresult(id) ON DELETE CASCADE,
    secondary_result_id INTEGER REFERENCES paperless_ai_ocr_ocrresult(id) ON DELETE CASCADE,
    additional_results_ids JSON, -- Array d'IDs pour plus de 2 moteurs

    -- Stratégie de fusion utilisée
    fusion_strategy VARCHAR(64) NOT NULL,
    fusion_parameters JSON,

    -- Résultat fusionné
    fused_text TEXT NOT NULL,
    fused_bounding_boxes JSON,

    -- Métriques de fusion
    overall_confidence DECIMAL(5,4),
    improvement_score DECIMAL(5,4), -- Amélioration par rapport au meilleur moteur seul
    sections_improved INTEGER DEFAULT 0,
    sections_total INTEGER,

    -- Analyse comparative
    primary_engine_accuracy DECIMAL(5,4),
    secondary_engine_accuracy DECIMAL(5,4),
    fusion_accuracy DECIMAL(5,4),

    -- Performance
    fusion_time DECIMAL(8,3),
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT ocr_fusion_unique_document UNIQUE (document_id),
    CONSTRAINT ocr_fusion_different_results CHECK (primary_result_id != secondary_result_id),
    CONSTRAINT ocr_fusion_confidence_range CHECK (overall_confidence >= 0 AND overall_confidence <= 1),
    CONSTRAINT ocr_fusion_improvement_range CHECK (improvement_score >= -1 AND improvement_score <= 1)
);
```

## Modèles Calendrier

### 1. Événements Extraits

```sql
-- paperless_calendar_calendarevent
CREATE TABLE paperless_calendar_calendarevent (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents_document(id) ON DELETE CASCADE,

    -- Informations de l'événement
    title VARCHAR(256) NOT NULL,
    description TEXT,
    location VARCHAR(512),

    -- Dates et heures
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    all_day BOOLEAN DEFAULT false,
    timezone VARCHAR(64), -- IANA timezone

    -- Récurrence
    is_recurring BOOLEAN DEFAULT false,
    recurrence_rule TEXT, -- Format RRULE RFC 5545
    recurrence_exceptions JSON, -- Array de dates d'exception

    -- Type d'événement
    event_type VARCHAR(64) NOT NULL, -- 'appointment', 'deadline', 'meeting', 'reminder', 'birthday'
    category VARCHAR(128),
    priority INTEGER DEFAULT 0, -- 0=low, 1=normal, 2=high, 3=urgent

    -- Extraction et confiance
    extracted_confidence DECIMAL(5,4) NOT NULL,
    extraction_method VARCHAR(64) NOT NULL, -- 'regex', 'nlp', 'ai_model'
    source_text TEXT NOT NULL, -- Texte source qui a permis l'extraction
    source_position JSON, -- Position dans le document {page, start, end}

    -- Participants
    organizer VARCHAR(256),
    attendees JSON, -- Array of {name, email, status}

    -- Statut
    status VARCHAR(32) DEFAULT 'tentative', -- 'tentative', 'confirmed', 'cancelled'
    validation_status VARCHAR(32) DEFAULT 'pending', -- 'pending', 'validated', 'rejected'
    validated_by_user_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    validated_at TIMESTAMP WITH TIME ZONE,

    -- Export vers calendriers externes
    external_calendar_provider VARCHAR(64), -- 'google', 'outlook', 'caldav', etc.
    external_calendar_id VARCHAR(256),
    external_event_id VARCHAR(256),
    sync_status VARCHAR(32) DEFAULT 'not_synced', -- 'not_synced', 'synced', 'sync_failed'
    last_sync TIMESTAMP WITH TIME ZONE,
    sync_error TEXT,

    -- Métadonnées
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT calendar_event_confidence_range CHECK (extracted_confidence >= 0 AND extracted_confidence <= 1),
    CONSTRAINT calendar_event_priority_range CHECK (priority >= 0 AND priority <= 3),
    CONSTRAINT calendar_event_dates_valid CHECK (end_date IS NULL OR start_date <= end_date),
    CONSTRAINT calendar_event_status_valid CHECK (status IN ('tentative', 'confirmed', 'cancelled')),
    CONSTRAINT calendar_event_validation_valid CHECK (validation_status IN ('pending', 'validated', 'rejected'))
);
```

### 2. Configuration Calendrier

```sql
-- paperless_calendar_calendarconfig
CREATE TABLE paperless_calendar_calendarconfig (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,

    -- Extraction automatique
    auto_extraction_enabled BOOLEAN DEFAULT true,
    min_confidence_threshold DECIMAL(3,2) DEFAULT 0.70,
    event_types_to_extract JSON DEFAULT '["appointment", "deadline", "meeting"]',

    -- Calendriers externes
    default_calendar_provider VARCHAR(64),
    calendar_connections JSON, -- Array of {provider, calendar_id, credentials}

    -- Notifications
    notification_enabled BOOLEAN DEFAULT true,
    notification_methods JSON DEFAULT '["email"]', -- 'email', 'webhook', 'browser'
    notification_advance_days INTEGER DEFAULT 1,

    -- Paramètres d'export
    auto_export_enabled BOOLEAN DEFAULT false,
    export_validated_only BOOLEAN DEFAULT true,
    add_document_links BOOLEAN DEFAULT true,
    default_event_duration_minutes INTEGER DEFAULT 60,

    -- Métadonnées
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT calendar_config_unique_user UNIQUE (user_id),
    CONSTRAINT calendar_config_confidence_range CHECK (min_confidence_threshold >= 0 AND min_confidence_threshold <= 1),
    CONSTRAINT calendar_config_advance_positive CHECK (notification_advance_days >= 0)
);
```

## Modèles Mail IA

### 1. Configuration Mail IA

```sql
-- paperless_mail_ai_mailaiconfiguration
CREATE TABLE paperless_mail_ai_mailaiconfiguration (
    id SERIAL PRIMARY KEY,
    mail_account_id INTEGER NOT NULL REFERENCES paperless_mail_mailaccount(id) ON DELETE CASCADE,

    -- Fonctionnalités IA
    auto_categorization_enabled BOOLEAN DEFAULT true,
    smart_extraction_enabled BOOLEAN DEFAULT true,
    attachment_analysis_enabled BOOLEAN DEFAULT true,
    sender_learning_enabled BOOLEAN DEFAULT true,

    -- Seuils de confiance
    categorization_confidence_threshold DECIMAL(3,2) DEFAULT 0.75,
    extraction_confidence_threshold DECIMAL(3,2) DEFAULT 0.80,

    -- Règles automatiques
    auto_create_rules BOOLEAN DEFAULT false,
    auto_suggest_rules BOOLEAN DEFAULT true,
    rule_learning_period_days INTEGER DEFAULT 30,

    -- Traitement des pièces jointes
    analyze_attachments BOOLEAN DEFAULT true,
    extract_attachment_metadata BOOLEAN DEFAULT true,
    merge_related_documents BOOLEAN DEFAULT false,

    -- Notifications
    notify_new_suggestions BOOLEAN DEFAULT true,
    notify_classification_changes BOOLEAN DEFAULT false,

    -- Métadonnées
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT mail_ai_config_unique_account UNIQUE (mail_account_id),
    CONSTRAINT mail_ai_config_categorization_threshold_range CHECK (categorization_confidence_threshold >= 0 AND categorization_confidence_threshold <= 1),
    CONSTRAINT mail_ai_config_extraction_threshold_range CHECK (extraction_confidence_threshold >= 0 AND extraction_confidence_threshold <= 1),
    CONSTRAINT mail_ai_config_learning_period_positive CHECK (rule_learning_period_days > 0)
);
```

### 2. Résultats de Traitement Mail

```sql
-- paperless_mail_ai_mailprocessingresult
CREATE TABLE paperless_mail_ai_mailprocessingresult (
    id SERIAL PRIMARY KEY,
    mail_rule_id INTEGER REFERENCES paperless_mail_mailrule(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents_document(id) ON DELETE CASCADE,

    -- Métadonnées du mail source
    mail_subject TEXT,
    mail_sender VARCHAR(256),
    mail_date TIMESTAMP WITH TIME ZONE,
    mail_message_id VARCHAR(256),
    attachment_name VARCHAR(512),

    -- Classification automatique
    suggested_correspondent_id INTEGER REFERENCES documents_correspondent(id) ON DELETE SET NULL,
    suggested_document_type_id INTEGER REFERENCES documents_documenttype(id) ON DELETE SET NULL,
    suggested_storage_path_id INTEGER REFERENCES documents_storagepath(id) ON DELETE SET NULL,
    suggested_tags JSON, -- Array of tag IDs

    -- Confiance des suggestions
    correspondent_confidence DECIMAL(5,4),
    document_type_confidence DECIMAL(5,4),
    storage_path_confidence DECIMAL(5,4),
    tags_confidence JSON, -- Array of {tag_id, confidence}

    -- Entités extraites
    extracted_entities JSON, -- {dates, amounts, persons, organizations, etc.}

    -- Analyse du contenu
    content_summary TEXT,
    detected_language VARCHAR(8),
    business_category VARCHAR(128),
    urgency_level INTEGER DEFAULT 0, -- 0=low, 1=normal, 2=high, 3=urgent

    -- Apprentissage et amélioration
    user_feedback VARCHAR(32), -- 'accepted', 'rejected', 'modified'
    actual_correspondent_id INTEGER REFERENCES documents_correspondent(id) ON DELETE SET NULL,
    actual_document_type_id INTEGER REFERENCES documents_documenttype(id) ON DELETE SET NULL,
    actual_tags JSON, -- Array of actual tag IDs after user review

    -- Métriques
    processing_time DECIMAL(8,3),
    created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    feedback_received_at TIMESTAMP WITH TIME ZONE,

    -- Contraintes
    CONSTRAINT mail_processing_confidence_range CHECK (
        (correspondent_confidence IS NULL OR (correspondent_confidence >= 0 AND correspondent_confidence <= 1)) AND
        (document_type_confidence IS NULL OR (document_type_confidence >= 0 AND document_type_confidence <= 1)) AND
        (storage_path_confidence IS NULL OR (storage_path_confidence >= 0 AND storage_path_confidence <= 1))
    ),
    CONSTRAINT mail_processing_urgency_range CHECK (urgency_level >= 0 AND urgency_level <= 3),
    CONSTRAINT mail_processing_feedback_valid CHECK (user_feedback IS NULL OR user_feedback IN ('accepted', 'rejected', 'modified'))
);
```

## Extensions des modèles existants

### Extension du modèle Document

```sql
-- Ajout de colonnes au modèle documents_document existant
ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS ai_processing_status VARCHAR(32) DEFAULT 'pending';
ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS ai_confidence_score DECIMAL(5,4);
ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS semantic_summary TEXT;
ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS extracted_entities JSON DEFAULT '{}';
ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS ai_last_processed TIMESTAMP WITH TIME ZONE;
ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS ai_processing_version VARCHAR(32);

-- Contraintes pour les nouvelles colonnes
ALTER TABLE documents_document ADD CONSTRAINT document_ai_status_valid
    CHECK (ai_processing_status IN ('pending', 'processing', 'completed', 'failed', 'skipped'));
ALTER TABLE documents_document ADD CONSTRAINT document_ai_confidence_range
    CHECK (ai_confidence_score IS NULL OR (ai_confidence_score >= 0 AND ai_confidence_score <= 1));
```

### Extension du modèle PaperlessTask

```sql
-- Ajout de colonnes pour les tâches IA
ALTER TABLE documents_paperlesstask ADD COLUMN IF NOT EXISTS ai_analysis_types JSON;
ALTER TABLE documents_paperlesstask ADD COLUMN IF NOT EXISTS ai_progress_details JSON;
ALTER TABLE documents_paperlesstask ADD COLUMN IF NOT EXISTS resource_usage JSON;
ALTER TABLE documents_paperlesstask ADD COLUMN IF NOT EXISTS model_versions JSON;
```

## Index et contraintes

### Index de performance

```sql
-- Index pour recherche vectorielle et IA
CREATE INDEX CONCURRENTLY idx_document_embedding_model_version
    ON paperless_ai_engine_documentembedding(model_name, model_version);

CREATE INDEX CONCURRENTLY idx_document_embedding_document_updated
    ON paperless_ai_engine_documentembedding(document_id, updated DESC);

CREATE INDEX CONCURRENTLY idx_document_ai_status_score
    ON documents_document(ai_processing_status, ai_confidence_score DESC)
    WHERE ai_processing_status = 'completed';

-- Index pour requêtes sémantiques
CREATE INDEX CONCURRENTLY idx_semantic_query_user_created
    ON paperless_ai_engine_semanticquery(user_id, created DESC);

CREATE INDEX CONCURRENTLY idx_semantic_query_performance
    ON paperless_ai_engine_semanticquery(total_time, results_count);

-- Index pour OCR
CREATE INDEX CONCURRENTLY idx_ocr_result_document_engine
    ON paperless_ai_ocr_ocrresult(document_id, engine, created DESC);

CREATE INDEX CONCURRENTLY idx_ocr_result_confidence
    ON paperless_ai_ocr_ocrresult(overall_confidence DESC)
    WHERE status = 'completed';

-- Index pour calendrier
CREATE INDEX CONCURRENTLY idx_calendar_event_dates
    ON paperless_calendar_calendarevent(start_date, end_date);

CREATE INDEX CONCURRENTLY idx_calendar_event_document_confidence
    ON paperless_calendar_calendarevent(document_id, extracted_confidence DESC);

CREATE INDEX CONCURRENTLY idx_calendar_event_sync_status
    ON paperless_calendar_calendarevent(sync_status, last_sync);

-- Index pour mail IA
CREATE INDEX CONCURRENTLY idx_mail_processing_rule_created
    ON paperless_mail_ai_mailprocessingresult(mail_rule_id, created DESC);

CREATE INDEX CONCURRENTLY idx_mail_processing_feedback
    ON paperless_mail_ai_mailprocessingresult(user_feedback, feedback_received_at);
```

### Contraintes d'intégrité

```sql
-- Contraintes pour cohérence des données IA
ALTER TABLE paperless_ai_engine_documentembedding
ADD CONSTRAINT embedding_vector_not_empty
CHECK (JSON_ARRAY_LENGTH(embedding_vector) = embedding_dimension);

-- Contraintes pour OCR
ALTER TABLE paperless_ai_ocr_ocrresult
ADD CONSTRAINT ocr_result_text_consistency
CHECK ((extracted_text IS NULL) = (text_length IS NULL OR text_length = 0));

-- Contraintes pour calendrier
ALTER TABLE paperless_calendar_calendarevent
ADD CONSTRAINT calendar_event_external_consistency
CHECK (
    (external_calendar_id IS NULL AND external_event_id IS NULL AND sync_status = 'not_synced') OR
    (external_calendar_id IS NOT NULL AND sync_status != 'not_synced')
);
```

## Migrations

### Migration 1060 - Tables de base IA

```python
# paperless_ai_engine/migrations/0001_initial.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('documents', '1059_last_existing_migration'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, default='default')),
                ('embedding_model', models.CharField(max_length=256, default='distilbert-base-multilingual-cased')),
                ('embedding_dimension', models.PositiveIntegerField(default=768)),
                # ... autres champs
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'AI Configuration',
                'verbose_name_plural': 'AI Configurations',
            },
        ),
        # ... autres modèles
    ]
```

### Migration 1061 - Embeddings et OCR

```python
# paperless_ai_engine/migrations/0002_embeddings_ocr.py
class Migration(migrations.Migration):
    dependencies = [
        ('paperless_ai_engine', '0001_initial'),
        ('paperless_ai_ocr', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentEmbedding',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True)),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='documents.Document')),
                ('embedding_vector', models.JSONField()),
                # ... autres champs
            ],
        ),
        # Création des index
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY idx_document_embedding_model_version ON paperless_ai_engine_documentembedding(model_name, model_version);",
            reverse_sql="DROP INDEX idx_document_embedding_model_version;"
        ),
    ]
```

### Migration 1062 - Extension Document existant

```python
# documents/migrations/1062_extend_document_ai.py
class Migration(migrations.Migration):
    dependencies = [
        ('documents', '1061_previous_migration'),
        ('paperless_ai_engine', '0002_embeddings_ocr'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='ai_processing_status',
            field=models.CharField(
                max_length=32,
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('skipped', 'Skipped'),
                ],
                default='pending'
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='ai_confidence_score',
            field=models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True),
        ),
        # ... autres champs
    ]
```

## Vues et fonctions

### Vues de performance

```sql
-- Vue pour statistiques de performance IA
CREATE VIEW v_ai_performance_stats AS
SELECT
    DATE_TRUNC('day', created) as date,
    COUNT(*) as total_analyses,
    AVG(processing_time) as avg_processing_time,
    AVG(confidence_score) as avg_confidence,
    COUNT(*) FILTER (WHERE confidence_score >= 0.8) as high_confidence_count,
    analysis_type
FROM paperless_ai_engine_aianalysisresult
WHERE status = 'completed'
GROUP BY DATE_TRUNC('day', created), analysis_type
ORDER BY date DESC;

-- Vue pour documents nécessitant reprocessing IA
CREATE VIEW v_documents_need_ai_reprocessing AS
SELECT
    d.id,
    d.title,
    d.modified,
    d.ai_last_processed,
    CASE
        WHEN d.ai_last_processed IS NULL THEN 'never_processed'
        WHEN d.modified > d.ai_last_processed THEN 'content_updated'
        WHEN ac.updated > d.ai_last_processed THEN 'config_updated'
        ELSE 'up_to_date'
    END as reprocessing_reason
FROM documents_document d
CROSS JOIN paperless_ai_engine_aiconfiguration ac
WHERE ac.is_active = true
AND (
    d.ai_last_processed IS NULL
    OR d.modified > d.ai_last_processed
    OR ac.updated > d.ai_last_processed
);
```

### Fonctions utilitaires

```sql
-- Fonction pour calculer la similarité cosine
CREATE OR REPLACE FUNCTION cosine_similarity(vector1 JSONB, vector2 JSONB)
RETURNS DECIMAL(5,4) AS $$
DECLARE
    dot_product DECIMAL := 0;
    norm1 DECIMAL := 0;
    norm2 DECIMAL := 0;
    i INTEGER;
    v1_array DECIMAL[];
    v2_array DECIMAL[];
BEGIN
    -- Convertir les JSON en arrays
    SELECT ARRAY(SELECT jsonb_array_elements_text(vector1)::DECIMAL) INTO v1_array;
    SELECT ARRAY(SELECT jsonb_array_elements_text(vector2)::DECIMAL) INTO v2_array;

    -- Vérifier que les vecteurs ont la même dimension
    IF array_length(v1_array, 1) != array_length(v2_array, 1) THEN
        RETURN NULL;
    END IF;

    -- Calculer le produit scalaire et les normes
    FOR i IN 1..array_length(v1_array, 1) LOOP
        dot_product := dot_product + (v1_array[i] * v2_array[i]);
        norm1 := norm1 + (v1_array[i] * v1_array[i]);
        norm2 := norm2 + (v2_array[i] * v2_array[i]);
    END LOOP;

    -- Éviter la division par zéro
    IF norm1 = 0 OR norm2 = 0 THEN
        RETURN 0;
    END IF;

    RETURN dot_product / (sqrt(norm1) * sqrt(norm2));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fonction pour nettoyer les anciens résultats d'analyse
CREATE OR REPLACE FUNCTION cleanup_old_ai_results(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Supprimer les anciens résultats d'analyse
    DELETE FROM paperless_ai_engine_aianalysisresult
    WHERE created < NOW() - INTERVAL '1 day' * retention_days
    AND status IN ('completed', 'failed');

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Supprimer les anciennes requêtes sémantiques
    DELETE FROM paperless_ai_engine_semanticquery
    WHERE created < NOW() - INTERVAL '1 day' * retention_days;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

### Triggers pour maintenance automatique

```sql
-- Trigger pour mettre à jour le statut de traitement IA
CREATE OR REPLACE FUNCTION update_ai_processing_status()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Mettre à jour le statut du document
        UPDATE documents_document
        SET ai_last_processed = NEW.created,
            ai_processing_status = CASE NEW.status
                WHEN 'completed' THEN 'completed'
                WHEN 'failed' THEN 'failed'
                ELSE ai_processing_status
            END,
            ai_confidence_score = CASE
                WHEN NEW.status = 'completed' THEN NEW.confidence_score
                ELSE ai_confidence_score
            END
        WHERE id = NEW.document_id;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_ai_analysis_result_update_document
    AFTER INSERT OR UPDATE ON paperless_ai_engine_aianalysisresult
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_processing_status();

-- Trigger pour invalider les embeddings obsolètes
CREATE OR REPLACE FUNCTION invalidate_outdated_embeddings()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.content != NEW.content THEN
        -- Marquer les embeddings comme obsolètes quand le contenu change
        UPDATE paperless_ai_engine_documentembedding
        SET model_version = model_version || '_outdated'
        WHERE document_id = NEW.id
        AND model_version NOT LIKE '%_outdated';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_document_content_change_invalidate_embeddings
    AFTER UPDATE OF content ON documents_document
    FOR EACH ROW
    EXECUTE FUNCTION invalidate_outdated_embeddings();
```

Ces schémas de base de données fournissent une fondation robuste et extensible pour les fonctionnalités d'IA de Paperless-ngx, avec des mécanismes de performance, d'intégrité et de maintenance automatique intégrés.
