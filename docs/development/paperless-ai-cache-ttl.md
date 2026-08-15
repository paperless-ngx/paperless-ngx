# Paperless-AI Cache-TTL Feature

## Problem
Kein konfigurierbarer Cache-TTL für AI-Suggestions; kein asynchrones Warm-up nach Consume.

## Lösung
- `PAPERLESS_AI_CACHE_TTL` als env-var (Standard 3600s) in `paperless/settings/__init__.py`.
- `documents/caching.py`: `set_llm_suggestions_cache`, `refresh_suggestions_cache` nutzen `settings.PAPERLESS_AI_CACHE_TTL` als Default.
- `documents/views.py`: Neue TTL geladen.
- `documents/tasks.py`: Neuer Celery-Task `warm_ai_suggestions_after_consume(document_id)`.
- `documents/signals/handlers.py`: `post_save`-Receiver `warm_ai_after_consume` triggert Task nur bei `created=True` und `AI_ENABLED`.

## Betroffene Dateien
- `paperless-ngx/src/paperless/settings/__init__.py`
- `paperless-ngx/src/documents/caching.py`
- `paperless-ngx/src/documents/views.py`
- `paperless-ngx/src/documents/tasks.py`
- `paperless-ngx/src/documents/signals/handlers.py`

## Status
Implementiert lokal. Dokumentation aktualisiert.
