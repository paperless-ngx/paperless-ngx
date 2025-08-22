# Spécifications des APIs - Extension Paperless-ngx

## Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [APIs de recherche sémantique](#apis-de-recherche-sémantique)
3. [APIs de traitement IA](#apis-de-traitement-ia)
4. [APIs OCR hybride](#apis-ocr-hybride)
5. [APIs calendrier intelligent](#apis-calendrier-intelligent)
6. [APIs de configuration](#apis-de-configuration)
7. [Codes d'erreur](#codes-derreur)
8. [Exemples d'utilisation](#exemples-dutilisation)

## Vue d'ensemble

Les nouvelles APIs étendent l'API REST existante de Paperless-ngx en conservant la cohérence avec les patterns établis. Toutes les APIs utilisent l'authentification par token et respectent le système de permissions existant.

### Base URL
```
https://your-paperless-instance.com/api/
```

### Format de réponse standard
```json
{
  "results": [...],
  "count": 42,
  "next": "https://api/endpoint/?page=2",
  "previous": null
}
```

## APIs de recherche sémantique

### POST /api/semantic_search/

Effectue une recherche sémantique sur le contenu des documents.

#### Paramètres
```json
{
  "query": "contrat de location appartement Paris",
  "limit": 20,
  "similarity_threshold": 0.7,
  "filters": {
    "document_type": [1, 2],
    "tags": [5, 8],
    "correspondent": 3,
    "date_range": {
      "start": "2023-01-01",
      "end": "2024-12-31"
    }
  },
  "include_embeddings": false
}
```

#### Réponse
```json
{
  "results": [
    {
      "document_id": 123,
      "title": "Contrat de bail - Appartement 15ème",
      "similarity_score": 0.95,
      "content_preview": "Le présent contrat de location...",
      "matched_sections": [
        {
          "text": "appartement situé à Paris 15ème",
          "confidence": 0.92,
          "start_pos": 145,
          "end_pos": 178
        }
      ],
      "metadata": {
        "document_type": "Contrat",
        "correspondent": "Agence Immobilière",
        "tags": ["Location", "Immobilier", "Paris"],
        "created": "2023-06-15T10:30:00Z"
      }
    }
  ],
  "count": 15,
  "query_time": 0.245,
  "embedding_time": 0.032
}
```

### GET /api/semantic_search/similar/{document_id}/

Trouve des documents similaires à un document donné.

#### Paramètres de requête
- `limit` (int, défaut: 10) : Nombre de résultats
- `threshold` (float, défaut: 0.6) : Seuil de similarité

#### Réponse
```json
{
  "source_document": {
    "id": 123,
    "title": "Facture EDF Juillet 2024"
  },
  "similar_documents": [
    {
      "document_id": 124,
      "title": "Facture EDF Août 2024",
      "similarity_score": 0.89,
      "common_features": ["facture", "électricité", "EDF", "consommation"]
    }
  ],
  "count": 5
}
```

## APIs de traitement IA

### POST /api/documents/{id}/ai_analyze/

Lance une analyse IA complète d'un document.

#### Paramètres
```json
{
  "analysis_types": ["classification", "entity_extraction", "summarization"],
  "force_reprocess": false,
  "save_results": true
}
```

#### Réponse
```json
{
  "task_id": "ai_analyze_doc_123_20241201_143022",
  "status": "PENDING",
  "estimated_time": 45,
  "analysis_types": ["classification", "entity_extraction", "summarization"]
}
```

### GET /api/documents/{id}/ai_results/

Récupère les résultats d'analyse IA d'un document.

#### Réponse
```json
{
  "document_id": 123,
  "analysis_results": {
    "classification": {
      "suggested_type": "Facture",
      "confidence": 0.92,
      "suggested_correspondent": "EDF",
      "suggested_tags": ["Énergie", "Facture", "Mensuel"],
      "processing_time": 1.2
    },
    "entity_extraction": {
      "entities": [
        {
          "type": "DATE",
          "value": "2024-07-15",
          "text": "15 juillet 2024",
          "confidence": 0.95,
          "position": [145, 160]
        },
        {
          "type": "AMOUNT",
          "value": 89.45,
          "currency": "EUR",
          "text": "89,45 €",
          "confidence": 0.98,
          "position": [234, 241]
        },
        {
          "type": "PERSON",
          "value": "Jean Dupont",
          "text": "M. Jean Dupont",
          "confidence": 0.87,
          "position": [56, 70]
        }
      ],
      "processing_time": 0.8
    },
    "summarization": {
      "summary": "Facture d'électricité EDF de juillet 2024 pour M. Jean Dupont, montant de 89,45 € avec échéance au 15 août.",
      "key_points": [
        "Fournisseur: EDF",
        "Période: Juillet 2024",
        "Montant: 89,45 €",
        "Échéance: 15 août 2024"
      ],
      "confidence": 0.91,
      "processing_time": 2.1
    }
  },
  "overall_confidence": 0.92,
  "last_updated": "2024-12-01T14:35:22Z"
}
```

### POST /api/documents/batch_ai_analyze/

Lance l'analyse IA sur un lot de documents.

#### Paramètres
```json
{
  "document_ids": [123, 124, 125, 126],
  "analysis_types": ["classification", "entity_extraction"],
  "priority": "normal",
  "callback_url": "https://your-app.com/webhook/ai_complete"
}
```

#### Réponse
```json
{
  "batch_id": "batch_ai_20241201_143522",
  "task_ids": [
    "ai_analyze_doc_123_20241201_143522",
    "ai_analyze_doc_124_20241201_143523",
    "ai_analyze_doc_125_20241201_143524",
    "ai_analyze_doc_126_20241201_143525"
  ],
  "total_documents": 4,
  "estimated_total_time": 180,
  "status": "QUEUED"
}
```

### GET /api/ai_tasks/{task_id}/

Suit le progrès d'une tâche IA.

#### Réponse
```json
{
  "task_id": "ai_analyze_doc_123_20241201_143022",
  "status": "PROCESSING",
  "progress": 65,
  "current_step": "entity_extraction",
  "completed_steps": ["classification"],
  "remaining_steps": ["summarization"],
  "started_at": "2024-12-01T14:30:22Z",
  "estimated_completion": "2024-12-01T14:32:15Z",
  "error": null
}
```

## APIs OCR hybride

### POST /api/documents/{id}/ocr_reprocess/

Relance le traitement OCR avec le pipeline hybride.

#### Paramètres
```json
{
  "engines": ["tesseract", "doctr"],
  "fusion_strategy": "confidence",
  "confidence_threshold": 0.8,
  "languages": ["fra", "eng"],
  "preprocessing": {
    "deskew": true,
    "denoise": true,
    "enhance_contrast": true
  }
}
```

#### Réponse
```json
{
  "task_id": "ocr_hybrid_doc_123_20241201_144022",
  "status": "PENDING",
  "engines_config": {
    "primary": "tesseract",
    "secondary": "doctr",
    "fusion": "confidence"
  },
  "estimated_time": 30
}
```

### GET /api/documents/{id}/ocr_results/

Récupère tous les résultats OCR pour un document.

#### Réponse
```json
{
  "document_id": 123,
  "ocr_results": [
    {
      "id": 1,
      "engine": "tesseract",
      "confidence": 0.87,
      "text_length": 1245,
      "processing_time": 12.5,
      "bounding_boxes": [
        {
          "text": "FACTURE",
          "confidence": 0.95,
          "bbox": [120, 45, 180, 65],
          "page": 1
        }
      ],
      "created": "2024-12-01T14:40:22Z"
    },
    {
      "id": 2,
      "engine": "doctr",
      "confidence": 0.92,
      "text_length": 1238,
      "processing_time": 8.2,
      "bounding_boxes": [
        {
          "text": "FACTURE",
          "confidence": 0.98,
          "bbox": [121, 46, 179, 64],
          "page": 1
        }
      ],
      "created": "2024-12-01T14:40:35Z"
    }
  ],
  "fusion_result": {
    "final_text": "...",
    "overall_confidence": 0.94,
    "fusion_strategy": "confidence",
    "improved_sections": 23,
    "total_sections": 45
  }
}
```

### POST /api/ocr/compare_engines/

Compare les performances des moteurs OCR sur un document.

#### Paramètres
```json
{
  "document_id": 123,
  "engines": ["tesseract", "doctr"],
  "metrics": ["accuracy", "speed", "confidence"]
}
```

#### Réponse
```json
{
  "comparison_results": {
    "tesseract": {
      "accuracy_score": 0.87,
      "processing_time": 12.5,
      "avg_confidence": 0.84,
      "word_count": 342,
      "detected_languages": ["fra"]
    },
    "doctr": {
      "accuracy_score": 0.92,
      "processing_time": 8.2,
      "avg_confidence": 0.91,
      "word_count": 339,
      "detected_languages": ["fra"]
    }
  },
  "recommendation": {
    "best_engine": "doctr",
    "reason": "Higher accuracy and faster processing",
    "improvement_percentage": 5.7
  }
}
```

## APIs calendrier intelligent

### GET /api/calendar_events/

Liste les événements extraits des documents.

#### Paramètres de requête
- `document_id` (int) : Filtrer par document
- `start_date` (date) : Date de début
- `end_date` (date) : Date de fin
- `confidence_min` (float) : Confiance minimale

#### Réponse
```json
{
  "results": [
    {
      "id": 1,
      "document_id": 123,
      "title": "Rendez-vous médecin",
      "start_date": "2024-12-15T14:30:00Z",
      "end_date": "2024-12-15T15:30:00Z",
      "description": "Consultation Dr. Martin - Contrôle annuel",
      "extracted_confidence": 0.89,
      "source_text": "Rendez-vous fixé le 15 décembre à 14h30 chez Dr. Martin",
      "event_type": "appointment",
      "external_calendar_id": null,
      "created": "2024-12-01T14:45:22Z"
    }
  ],
  "count": 1
}
```

### POST /api/calendar_events/{id}/export/

Exporte un événement vers un calendrier externe.

#### Paramètres
```json
{
  "calendar_provider": "google",
  "calendar_id": "primary",
  "notify_attendees": true,
  "add_document_link": true
}
```

#### Réponse
```json
{
  "success": true,
  "external_event_id": "google_event_abc123",
  "calendar_url": "https://calendar.google.com/event?eid=abc123",
  "sync_status": "synchronized"
}
```

### POST /api/documents/{id}/extract_events/

Extrait les événements d'un document spécifique.

#### Paramètres
```json
{
  "event_types": ["appointment", "deadline", "meeting", "reminder"],
  "min_confidence": 0.7,
  "auto_export": false,
  "calendar_config": {
    "provider": "caldav",
    "calendar_url": "https://calendar.example.com/cal/user"
  }
}
```

#### Réponse
```json
{
  "task_id": "extract_events_doc_123_20241201_145022",
  "status": "PENDING",
  "document_id": 123,
  "event_types": ["appointment", "deadline", "meeting", "reminder"],
  "estimated_time": 15
}
```

## APIs de configuration

### GET /api/ai_config/

Récupère la configuration IA actuelle.

#### Réponse
```json
{
  "embedding_config": {
    "model_name": "distilbert-base-multilingual-cased",
    "dimension": 768,
    "batch_size": 16,
    "cache_embeddings": true
  },
  "llm_config": {
    "model_path": "/models/llama3-8b-instruct",
    "max_tokens": 2048,
    "temperature": 0.1,
    "gpu_enabled": false
  },
  "ocr_config": {
    "primary_engine": "tesseract",
    "secondary_engine": "doctr",
    "fusion_strategy": "confidence",
    "confidence_threshold": 0.8
  },
  "search_config": {
    "similarity_threshold": 0.7,
    "max_results": 50,
    "reranking_enabled": true
  },
  "resource_limits": {
    "max_memory_mb": 4096,
    "max_concurrent_tasks": 4,
    "task_timeout_seconds": 300
  },
  "enabled_features": [
    "semantic_search",
    "ai_classification",
    "entity_extraction",
    "calendar_extraction",
    "hybrid_ocr"
  ]
}
```

### PUT /api/ai_config/

Met à jour la configuration IA.

#### Paramètres
```json
{
  "embedding_config": {
    "batch_size": 32,
    "cache_embeddings": true
  },
  "search_config": {
    "similarity_threshold": 0.75
  },
  "enabled_features": [
    "semantic_search",
    "ai_classification",
    "hybrid_ocr"
  ]
}
```

#### Réponse
```json
{
  "success": true,
  "updated_fields": [
    "embedding_config.batch_size",
    "search_config.similarity_threshold",
    "enabled_features"
  ],
  "restart_required": false,
  "effective_immediately": true
}
```

### POST /api/ai_config/test/

Teste la configuration IA.

#### Paramètres
```json
{
  "test_types": ["embedding", "llm", "ocr", "search"],
  "sample_document_id": 123
}
```

#### Réponse
```json
{
  "test_results": {
    "embedding": {
      "status": "success",
      "model_loaded": true,
      "embedding_time": 0.45,
      "dimension": 768
    },
    "llm": {
      "status": "success",
      "model_loaded": true,
      "response_time": 2.1,
      "test_output": "Le modèle fonctionne correctement."
    },
    "ocr": {
      "tesseract": {
        "status": "success",
        "version": "5.3.0",
        "languages": ["eng", "fra", "deu"]
      },
      "doctr": {
        "status": "success",
        "version": "0.8.1",
        "model_loaded": true
      }
    },
    "search": {
      "status": "success",
      "index_size": 1250,
      "search_time": 0.023
    }
  },
  "overall_status": "healthy",
  "recommendations": [
    "Increase batch_size for better performance",
    "Enable GPU acceleration for LLM"
  ]
}
```

## Codes d'erreur

### Codes d'erreur spécifiques à l'IA

| Code | Message                     | Description                             |
| ---- | --------------------------- | --------------------------------------- |
| 4001 | AI_MODEL_NOT_LOADED         | Le modèle IA n'est pas chargé           |
| 4002 | EMBEDDING_GENERATION_FAILED | Échec de génération d'embedding         |
| 4003 | OCR_ENGINE_UNAVAILABLE      | Moteur OCR indisponible                 |
| 4004 | INSUFFICIENT_MEMORY         | Mémoire insuffisante pour le traitement |
| 4005 | AI_PROCESSING_TIMEOUT       | Timeout du traitement IA                |
| 4006 | VECTOR_SEARCH_FAILED        | Échec de la recherche vectorielle       |
| 4007 | LLM_INFERENCE_ERROR         | Erreur d'inférence du modèle de langage |
| 4008 | CALENDAR_EXTRACTION_FAILED  | Échec de l'extraction de calendrier     |
| 4009 | AI_CONFIG_INVALID           | Configuration IA invalide               |
| 4010 | FEATURE_DISABLED            | Fonctionnalité IA désactivée            |

### Format d'erreur

```json
{
  "error": {
    "code": 4002,
    "message": "EMBEDDING_GENERATION_FAILED",
    "detail": "Le modèle d'embedding n'a pas pu traiter le document en raison d'un contenu trop volumineux",
    "field": "document_content",
    "timestamp": "2024-12-01T14:55:22Z",
    "request_id": "req_abc123"
  }
}
```

## Exemples d'utilisation

### Recherche sémantique complète

```python
import requests

# Configuration
api_base = "https://your-paperless.com/api"
headers = {"Authorization": "Token your_token_here"}

# 1. Recherche sémantique
search_data = {
    "query": "factures électricité dernier trimestre",
    "limit": 10,
    "similarity_threshold": 0.8,
    "filters": {
        "document_type": [2],  # Factures
        "date_range": {
            "start": "2024-10-01",
            "end": "2024-12-31"
        }
    }
}

response = requests.post(
    f"{api_base}/semantic_search/",
    json=search_data,
    headers=headers
)
results = response.json()

print(f"Trouvé {results['count']} documents pertinents")
for doc in results['results']:
    print(f"- {doc['title']} (score: {doc['similarity_score']:.2f})")
```

### Analyse IA complète d'un document

```python
# 2. Analyse IA d'un document
doc_id = 123
analysis_data = {
    "analysis_types": ["classification", "entity_extraction", "summarization"],
    "save_results": True
}

# Lancer l'analyse
task_response = requests.post(
    f"{api_base}/documents/{doc_id}/ai_analyze/",
    json=analysis_data,
    headers=headers
)
task_id = task_response.json()['task_id']

# Suivre le progrès
import time
while True:
    status_response = requests.get(
        f"{api_base}/ai_tasks/{task_id}/",
        headers=headers
    )
    status = status_response.json()

    if status['status'] in ['SUCCESS', 'FAILURE']:
        break

    print(f"Progrès: {status['progress']}% - {status['current_step']}")
    time.sleep(2)

# Récupérer les résultats
if status['status'] == 'SUCCESS':
    results_response = requests.get(
        f"{api_base}/documents/{doc_id}/ai_results/",
        headers=headers
    )
    ai_results = results_response.json()

    print("Classification suggérée:", ai_results['analysis_results']['classification']['suggested_type'])
    print("Entités extraites:", len(ai_results['analysis_results']['entity_extraction']['entities']))
    print("Résumé:", ai_results['analysis_results']['summarization']['summary'])
```

### Extraction et export d'événements

```python
# 3. Extraction d'événements de calendrier
doc_id = 123
event_data = {
    "event_types": ["appointment", "deadline"],
    "min_confidence": 0.8,
    "auto_export": False
}

# Extraire les événements
extract_response = requests.post(
    f"{api_base}/documents/{doc_id}/extract_events/",
    json=event_data,
    headers=headers
)
task_id = extract_response.json()['task_id']

# Attendre la fin de l'extraction...
# (code de suivi similaire à l'exemple précédent)

# Récupérer les événements extraits
events_response = requests.get(
    f"{api_base}/calendar_events/?document_id={doc_id}",
    headers=headers
)
events = events_response.json()['results']

# Exporter vers Google Calendar
for event in events:
    if event['extracted_confidence'] > 0.85:
        export_data = {
            "calendar_provider": "google",
            "calendar_id": "primary",
            "notify_attendees": False,
            "add_document_link": True
        }

        export_response = requests.post(
            f"{api_base}/calendar_events/{event['id']}/export/",
            json=export_data,
            headers=headers
        )

        if export_response.json()['success']:
            print(f"Événement '{event['title']}' exporté vers Google Calendar")
```

### Configuration et monitoring

```python
# 4. Configuration et test du système IA
# Récupérer la configuration actuelle
config_response = requests.get(f"{api_base}/ai_config/", headers=headers)
current_config = config_response.json()

print("Configuration actuelle:")
print(f"- Modèle embedding: {current_config['embedding_config']['model_name']}")
print(f"- Fonctionnalités activées: {current_config['enabled_features']}")

# Tester la configuration
test_data = {
    "test_types": ["embedding", "llm", "search"],
    "sample_document_id": 123
}

test_response = requests.post(
    f"{api_base}/ai_config/test/",
    json=test_data,
    headers=headers
)
test_results = test_response.json()

print(f"\nÉtat du système: {test_results['overall_status']}")
for component, result in test_results['test_results'].items():
    print(f"- {component}: {result['status']}")

# Mettre à jour la configuration si nécessaire
if test_results['overall_status'] == 'healthy':
    new_config = {
        "search_config": {
            "similarity_threshold": 0.75,
            "max_results": 100
        }
    }

    update_response = requests.put(
        f"{api_base}/ai_config/",
        json=new_config,
        headers=headers
    )

    if update_response.json()['success']:
        print("Configuration mise à jour avec succès")
```

Ces spécifications d'API fournissent une interface complète et cohérente pour intégrer les fonctionnalités d'IA avancées dans Paperless-ngx, tout en maintenant la compatibilité avec l'architecture existante.
