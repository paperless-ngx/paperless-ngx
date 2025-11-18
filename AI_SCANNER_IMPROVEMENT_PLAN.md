# AI Scanner - Plan de Mejoras y Siguientes Pasos

## Documento de Planificación

**Fecha**: 2025-11-11
**Proyecto**: IntelliDocs-ngx AI Scanner
**Estado**: PRODUCTION READY - Mejoras Planificadas

---

## 📋 Resumen Ejecutivo

El sistema AI Scanner está completamente implementado y functional. Este documento detalla todas las mejoras, optimizaciones y tareas pendientes organizadas por prioridad y área.

---

## 🎯 Áreas de Mejora Identificadas

### 1. Testing y Calidad de Código

### 2. Migraciones de Base de Datos

### 3. API REST Endpoints

### 4. Integración Frontend

### 5. Optimización de Performance

### 6. Mejoras de ML/AI

### 7. Monitoreo y Observabilidad

### 8. Documentación de Usuario

### 9. Seguridad Avanzada

### 10. Internacionalización

---

## 📊 ÉPICA 1: Testing y Calidad de Código

### Issue 1.1: Tests Unitarios para AI Scanner

**Prioridad**: 🔴 ALTA
**Estimación**: 3-5 días
**Dependencias**: Ninguna

**Descripción**:
Crear suite completa de tests unitarios para `ai_scanner.py`

**Tareas**:

- [ ] Tests para `AIDocumentScanner.__init__()` y lazy loading
- [ ] Tests para `_extract_entities()` con mocks de NER
- [ ] Tests para `_suggest_tags()` con diferentes niveles de confianza
- [ ] Tests para `_detect_correspondent()` con y sin entidades
- [ ] Tests para `_classify_document_type()` con ML classifier mock
- [ ] Tests para `_suggest_storage_path()` con diferentes características
- [ ] Tests para `_extract_custom_fields()` con todos los tipos de campo
- [ ] Tests para `_suggest_workflows()` con varias condiciones
- [ ] Tests para `_suggest_title()` con diferentes combinaciones de entidades
- [ ] Tests para `apply_scan_results()` con transacciones atómicas
- [ ] Tests para manejo de errores y excepciones
- [ ] Alcanzar cobertura >90%

**Archivos a Crear**:

- `src/documents/tests/test_ai_scanner.py`
- `src/documents/tests/test_ai_scanner_integration.py`

**Criterios de Aceptación**:

- Cobertura de código >90% para ai_scanner.py
- Todos los tests pasan en CI/CD
- Tests incluyen casos edge y errores

---

### Issue 1.2: Tests Unitarios para AI Deletion Manager

**Prioridad**: 🔴 ALTA
**Estimación**: 2-3 días
**Dependencias**: Ninguna

**Descripción**:
Crear tests para `ai_deletion_manager.py` y modelo `DeletionRequest`

**Tareas**:

- [ ] Tests para `create_deletion_request()` con análisis de impacto
- [ ] Tests para `_analyze_impact()` con diferentes documentos
- [ ] Tests para `format_deletion_request_for_user()` con various escenarios
- [ ] Tests para `get_pending_requests()` con filtros
- [ ] Tests para modelo `DeletionRequest` (approve, reject)
- [ ] Tests para workflow completo de aprobación/rechazo
- [ ] Tests para auditoría y tracking
- [ ] Tests que verifiquen que AI nunca puede eliminar sin aprobación

**Archivos a Crear**:

- `src/documents/tests/test_ai_deletion_manager.py`
- `src/documents/tests/test_deletion_request_model.py`

**Criterios de Aceptación**:

- Cobertura >95% para components críticos de seguridad
- Tests verifican constraints de seguridad
- Tests pasan en CI/CD

---

### Issue 1.3: Tests de Integración para Consumer

**Prioridad**: 🔴 ALTA
**Estimación**: 2-3 días
**Dependencias**: Issue 1.1

**Descripción**:
Tests de integración para `_run_ai_scanner()` en pipeline de consumo

**Tareas**:

- [ ] Test de integración end-to-end: upload → consumo → AI scan → metadata
- [ ] Test con ML components deshabilitados
- [ ] Test con fallos de AI scanner (graceful degradation)
- [ ] Test con diferentes tipos de documentos (PDF, imagen, texto)
- [ ] Test de performance con documentos grandes
- [ ] Test con transacciones y rollbacks
- [ ] Test con múltiples documentos simultáneos

**Archivos a Modificar**:

- `src/documents/tests/test_consumer.py` (añadir tests AI)

**Criterios de Aceptación**:

- Pipeline completo testeado end-to-end
- Graceful degradation verificado
- Performance acceptable (<2s adicionales por documento)

---

### Issue 1.4: Pre-commit Hooks y Linting

**Prioridad**: 🟡 MEDIA
**Estimación**: 1 día
**Dependencias**: Ninguna

**Descripción**:
Ejecutar y corregir linters en código nuevo

**Tareas**:

- [ ] Ejecutar `ruff` en archivos nuevos
- [ ] Corregir warnings de import ordering
- [ ] Corregir warnings de type hints
- [ ] Ejecutar `black` para formateo consistente
- [ ] Ejecutar `mypy` para verificación de tipos
- [ ] Actualizar pre-commit hooks si necesario

**Archivos a Revisar**:

- `src/documents/ai_scanner.py`
- `src/documents/ai_deletion_manager.py`
- `src/documents/consumer.py`

**Criterios de Aceptación**:

- Cero warnings de linters
- Código pasa pre-commit hooks
- Type hints completos

---

## 📊 ÉPICA 2: Migraciones de Base de Datos

### Issue 2.1: Migración Django para DeletionRequest

**Prioridad**: 🔴 ALTA
**Estimación**: 1 día
**Dependencias**: Issue 1.2 (tests)

**Descripción**:
Crear migración Django para modelo `DeletionRequest`

**Tareas**:

- [ ] Ejecutar `python manage.py makemigrations`
- [ ] Revisar migración generada
- [ ] Añadir índices custom si necesario
- [ ] Crear migración de datos si hay datos existentes
- [ ] Testear migración en entorno dev
- [ ] Documentar pasos de migración

**Archivos a Crear**:

- `src/documents/migrations/XXXX_add_deletion_request.py`

**Criterios de Aceptación**:

- Migración se ejecuta sin errores
- Índices creados correctamente
- Backward compatible si possible

---

### Issue 2.2: Índices de Performance para DeletionRequest

**Prioridad**: 🟡 MEDIA
**Estimación**: 0.5 días
**Dependencias**: Issue 2.1

**Descripción**:
Optimizar índices de base de datos para queries frecuentes

**Tareas**:

- [ ] Analizar queries frecuentes
- [ ] Añadir índice compuesto (user, status, created_at)
- [ ] Añadir índice para reviewed_at
- [ ] Añadir índice para completed_at
- [ ] Testear performance de queries

**Archivos a Modificar**:

- `src/documents/models.py` (añadir índices)

**Criterios de Aceptación**:

- Queries de listado <100ms
- Queries de filtrado <50ms

---

## 📊 ÉPICA 3: API REST Endpoints

### Issue 3.1: API Endpoints para Deletion Requests - Listado y Detalle

**Prioridad**: 🔴 ALTA
**Estimación**: 2-3 días
**Dependencias**: Issue 2.1

**Descripción**:
Crear endpoints REST para gestión de deletion requests

**Tareas**:

- [ ] Crear serializer `DeletionRequestSerializer`
- [ ] Endpoint GET `/api/deletion-requests/` (listado paginado)
- [ ] Endpoint GET `/api/deletion-requests/{id}/` (detalle)
- [ ] Filtros: status, user, date_range
- [ ] Ordenamiento: created_at, reviewed_at
- [ ] Paginación (page size: 20)
- [ ] Documentación OpenAPI/Swagger

**Archivos a Crear**:

- `src/documents/serializers/deletion_request.py`
- `src/documents/views/deletion_request.py`
- Actualizar `src/documents/urls.py`

**Criterios de Aceptación**:

- Endpoints documentados en Swagger
- Tests de API incluidos
- Permisos verificados (solo requests propios o admin)

---

### Issue 3.2: API Endpoints para Deletion Requests - Acciones

**Prioridad**: 🔴 ALTA
**Estimación**: 2 días
**Dependencias**: Issue 3.1

**Descripción**:
Endpoints para aprobar/rechazar deletion requests

**Tareas**:

- [ ] Endpoint POST `/api/deletion-requests/{id}/approve/`
- [ ] Endpoint POST `/api/deletion-requests/{id}/reject/`
- [ ] Endpoint POST `/api/deletion-requests/{id}/cancel/`
- [ ] Validación de permisos (solo owner o admin)
- [ ] Validación de estado (solo pending puede set aprobado/rechazado)
- [ ] Respuesta con resultado de ejecución si aprobado
- [ ] Notificaciones async si configurado

**Archivos a Modificar**:

- `src/documents/views/deletion_request.py`
- Actualizar `src/documents/urls.py`

**Criterios de Aceptación**:

- Workflow completo functional via API
- Validaciones de estado y permisos
- Tests de API incluidos

---

### Issue 3.3: API Endpoints para AI Suggestions

**Prioridad**: 🟡 MEDIA
**Estimación**: 2-3 días
**Dependencias**: Ninguna

**Descripción**:
Exponer sugerencias de AI via API para frontend

**Tareas**:

- [ ] Endpoint GET `/api/documents/{id}/ai-suggestions/`
- [ ] Serializer para `AIScanResult`
- [ ] Endpoint POST `/api/documents/{id}/apply-suggestion/`
- [ ] Endpoint POST `/api/documents/{id}/reject-suggestion/`
- [ ] Tracking de sugerencias aplicadas/rechazadas
- [ ] Estadísticas de accuracy de sugerencias

**Archivos a Crear**:

- `src/documents/serializers/ai_suggestions.py`
- Actualizar `src/documents/views/document.py`

**Criterios de Aceptación**:

- Frontend puede obtener y aplicar sugerencias
- Tracking de user feedback
- API documentada

---

### Issue 3.4: Webhooks para Eventos de AI

**Prioridad**: 🟢 BAJA
**Estimación**: 2 días
**Dependencias**: Issue 3.1, 3.3

**Descripción**:
Sistema de webhooks para notificar eventos de AI

**Tareas**:

- [ ] Webhook cuando AI crea deletion request
- [ ] Webhook cuando AI aplica sugerencia automáticamente
- [ ] Webhook cuando scan AI completa
- [ ] Configuración de webhooks via settings
- [ ] Retry logic con exponential backoff
- [ ] Logging de webhooks enviados

**Archivos a Crear**:

- `src/documents/webhooks.py`
- Actualizar `src/paperless/settings.py`

**Criterios de Aceptación**:

- Webhooks configurables
- Retry logic robusto
- Eventos documentados

---

## 📊 ÉPICA 4: Integración Frontend

### Issue 4.1: UI para AI Suggestions en Document Detail

**Prioridad**: 🔴 ALTA
**Estimación**: 3-4 días
**Dependencias**: Issue 3.3

**Descripción**:
Mostrar sugerencias de AI en página de detalle de documento

**Tareas**:

- [ ] Componente `AISuggestionsPanel` en Angular/React
- [ ] Mostrar sugerencias por tipo (tags, correspondent, etc.)
- [ ] Indicadores de confianza visual (colores, iconos)
- [ ] Botones "Aplicar" y "Rechazar" por sugerencia
- [ ] Animaciones de aplicación
- [ ] Feedback visual cuando se aplica
- [ ] Responsive design

**Archivos a Crear**:

- `src-ui/src/app/components/ai-suggestions-panel/`
- Actualizar componente de document detail

**Criterios de Aceptación**:

- UI intuitiva y atractiva
- Mobile responsive
- Tests de componente incluidos

---

### Issue 4.2: UI para Deletion Requests Management

**Prioridad**: 🔴 ALTA
**Estimación**: 3-4 días
**Dependencias**: Issue 3.1, 3.2

**Descripción**:
Dashboard para gestionar deletion requests

**Tareas**:

- [ ] Página `/deletion-requests` con listado
- [ ] Filtros por estado (pending, approved, rejected)
- [ ] Vista detalle de deletion request con impacto completo
- [ ] Modal de confirmación para aprobar/rechazar
- [ ] Mostrar análisis de impacto de forma clara
- [ ] Badge de notificación para pending requests
- [ ] Historical de requests completados

**Archivos a Crear**:

- `src-ui/src/app/components/deletion-requests/`
- `src-ui/src/app/services/deletion-request.service.ts`

**Criterios de Aceptación**:

- Usuario puede revisar y aprobar/rechazar requests
- Análisis de impacto claro y comprensible
- Notificaciones visuals

---

### Issue 4.3: AI Status Indicator

**Prioridad**: 🟡 MEDIA
**Estimación**: 1-2 días
**Dependencias**: Ninguna

**Descripción**:
Indicador global de estado de AI en UI

**Tareas**:

- [ ] Icono en navbar mostrando estado de AI (activo/inactivo)
- [ ] Tooltip con estadísticas (documentos escaneados hoy, sugerencias aplicadas)
- [ ] Link a configuración de AI
- [ ] Mostrar si hay pending deletion requests
- [ ] Animación cuando AI está procesando

**Archivos a Modificar**:

- Navbar component
- Crear servicio de AI status

**Criterios de Aceptación**:

- Estado de AI siempre visible
- Notificaciones no intrusivas

---

### Issue 4.4: Settings Page para AI Configuration

**Prioridad**: 🟡 MEDIA
**Estimación**: 2-3 días
**Dependencias**: Ninguna

**Descripción**:
Página de configuración para features de AI

**Tareas**:

- [ ] Toggle para enable/disable AI scanner
- [ ] Toggle para enable/disable ML features
- [ ] Toggle para enable/disable advanced OCR
- [ ] Sliders para thresholds (auto-apply, suggest)
- [ ] Selector de modelo ML
- [ ] Test button para probar AI con documento sample
- [ ] Estadísticas de performance de AI

**Archivos a Crear**:

- `src-ui/src/app/components/settings/ai-settings/`

**Criterios de Aceptación**:

- Configuración intuitiva y clara
- Cambios se reflejan inmediatamente
- Validación de valores

---

## 📊 ÉPICA 5: Optimización de Performance

### Issue 5.1: Caching de Modelos ML

**Prioridad**: 🔴 ALTA
**Estimación**: 2 días
**Dependencias**: Ninguna

**Descripción**:
Implementar caché eficiente para modelos ML

**Tareas**:

- [ ] Implementar singleton pattern para modelos ML
- [ ] Caché en memoria con LRU eviction
- [ ] Caché en disco para embeddings
- [ ] Lazy loading mejorado con preloading opcional
- [ ] Warm-up de modelos en startup si configurado
- [ ] Métricas de cache hits/misses

**Archivos a Modificar**:

- `src/documents/ai_scanner.py`
- `src/documents/ml/*.py`

**Criterios de Aceptación**:

- Primera carga lenta, subsecuentes rápidas
- Uso de memoria controlado (<2GB)
- Cache hits >90% después de warm-up

---

### Issue 5.2: Procesamiento Asíncrono con Celery

**Prioridad**: 🟡 MEDIA
**Estimación**: 2-3 días
**Dependencias**: Issue 5.1

**Descripción**:
Mover AI scanning a tareas Celery asíncronas

**Tareas**:

- [ ] Crear tarea Celery `scan_document_ai`
- [ ] Queue separada para AI tasks (priority: low)
- [ ] Rate limiting para AI tasks
- [ ] Progress tracking para scans largos
- [ ] Retry logic para fallos temporales
- [ ] Configurar workers dedicados para AI

**Archivos a Crear**:

- `src/documents/tasks/ai_scanner_tasks.py`
- Actualizar `src/documents/consumer.py`

**Criterios de Aceptación**:

- Consumo de documentos no bloqueado por AI
- AI procesa en background
- Progress visible en UI

---

### Issue 5.3: Batch Processing para Documentos Existentes

**Prioridad**: 🟡 MEDIA
**Estimación**: 2 días
**Dependencias**: Issue 5.2

**Descripción**:
Command para aplicar AI scanner a documentos existentes

**Tareas**:

- [ ] Management command `scan_documents_ai`
- [ ] Opciones: --all, --filter-by-type, --date-range
- [ ] Progress bar con ETA
- [ ] Dry-run mode
- [ ] Resumen de sugerencias al final
- [ ] Opción para auto-apply high confidence

**Archivos a Crear**:

- `src/documents/management/commands/scan_documents_ai.py`

**Criterios de Aceptación**:

- Puede procesar miles de documentos
- No afecta performance del sistema
- Resultados reportados claramente

---

### Issue 5.4: Query Optimization

**Prioridad**: 🟡 MEDIA
**Estimación**: 1-2 días
**Dependencias**: Ninguna

**Descripción**:
Optimizar queries de base de datos en AI scanner

**Tareas**:

- [ ] Usar select_related() para foreign keys
- [ ] Usar prefetch_related() para M2M
- [ ] Cachear queries frecuentes (tags, correspondents)
- [ ] Analizar slow queries con Django Debug Toolbar
- [ ] Optimizar N+1 queries si existen

**Archivos a Modificar**:

- `src/documents/ai_scanner.py`
- `src/documents/ai_deletion_manager.py`

**Criterios de Aceptación**:

- Número de queries reducido >50%
- Tiempo de scan reducido >30%

---

## 📊 ÉPICA 6: Mejoras de ML/AI

### Issue 6.1: Training Pipeline para Custom Models

**Prioridad**: 🟡 MEDIA
**Estimación**: 3-4 días
**Dependencias**: Issue 1.1

**Descripción**:
Pipeline para entrenar modelos custom con datos del usuario

**Tareas**:

- [ ] Recolectar datos de training (documentos + metadata confirmada)
- [ ] Script de preparación de datos
- [ ] Training script con hyperparameter tuning
- [ ] Evaluación de modelo (accuracy, precision, recall)
- [ ] Versionado de modelos
- [ ] A/B testing de modelos

**Archivos a Crear**:

- `src/documents/ml/training/`
- `scripts/train_classifier.py`

**Criterios de Aceptación**:

- Pipeline reproducible
- Métricas de evaluación claras
- Modelos mejorados vs baseline

---

### Issue 6.2: Active Learning Loop

**Prioridad**: 🟢 BAJA
**Estimación**: 3-5 días
**Dependencias**: Issue 6.1, Issue 3.3

**Descripción**:
Sistema de aprendizaje continuo basado en feedback de usuario

**Tareas**:

- [ ] Tracking de sugerencias aceptadas/rechazadas
- [ ] Identificar casos difíciles (low confidence)
- [ ] Re-training periódico con nuevos datos
- [ ] Métricas de mejora de accuracy over time
- [ ] Dashboard de ML performance

**Archivos a Crear**:

- `src/documents/ml/active_learning.py`

**Criterios de Aceptación**:

- Accuracy mejora con uso
- Re-training automático configurable

---

### Issue 6.3: Multi-language Support para NER

**Prioridad**: 🟡 MEDIA
**Estimación**: 2-3 días
**Dependencias**: Ninguna

**Descripción**:
Soporte para múltiples idiomas en extracción de entidades

**Tareas**:

- [ ] Detección automática de idioma
- [ ] Modelos NER multilingües
- [ ] Fallback a inglés si idioma no soportado
- [ ] Tests con documentos en español, francés, alemán
- [ ] Configuración de idiomas soportados

**Archivos a Modificar**:

- `src/documents/ml/ner.py`
- `src/paperless/settings.py`

**Criterios de Aceptación**:

- Funciona con español, inglés, francés, alemán
- Accuracy >80% en cada idioma

---

### Issue 6.4: Confidence Calibration

**Prioridad**: 🟡 MEDIA
**Estimación**: 2 días
**Dependencias**: Issue 3.3

**Descripción**:
Calibrar confianza basada en feedback histórico

**Tareas**:

- [ ] Analizar correlación entre confianza y accuracy real
- [ ] Ajustar thresholds automáticamente
- [ ] Calibración por tipo de sugerencia
- [ ] Calibración por usuario (si user acepta todas, subir threshold)
- [ ] Tests de calibración

**Archivos a Modificar**:

- `src/documents/ai_scanner.py`

**Criterios de Aceptación**:

- Confianza correlaciona con accuracy
- Auto-apply solo cuando realmente correcto >95%

---

## 📊 ÉPICA 7: Monitoreo y Observabilidad

### Issue 7.1: Metrics y Logging Estructurado

**Prioridad**: 🟡 MEDIA
**Estimación**: 2 días
**Dependencias**: Ninguna

**Descripción**:
Implementar logging estructurado y métricas

**Tareas**:

- [ ] Logging estructurado (JSON) con contexto
- [ ] Métricas Prometheus: ai_scans_total, ai_scan_duration_seconds
- [ ] Métricas de sugerencias: applied, rejected, ignored
- [ ] Métricas de confianza por tipo
- [ ] Alertas para errores de AI (>5% failure rate)
- [ ] Dashboard Grafana

**Archivos a Crear**:

- `src/documents/metrics.py`
- Configuración Prometheus

**Criterios de Aceptación**:

- Métricas exportadas a Prometheus
- Dashboard básico en Grafana
- Alertas configuradas

---

### Issue 7.2: Health Checks para AI Components

**Prioridad**: 🟡 MEDIA
**Estimación**: 1 día
**Dependencias**: Issue 7.1

**Descripción**:
Health checks para components ML/AI

**Tareas**:

- [ ] Endpoint `/health/ai/` con status de components
- [ ] Check si modelos cargados correctamente
- [ ] Check si NER functional
- [ ] Check uso de memoria
- [ ] Check GPU si habilitado
- [ ] Incluir en health check general

**Archivos a Crear**:

- `src/documents/health_checks.py`

**Criterios de Aceptación**:

- Health check responde rápido (<100ms)
- Indica qué componente falla

---

### Issue 7.3: Audit Log Detallado

**Prioridad**: 🟡 MEDIA
**Estimación**: 1-2 días
**Dependencias**: Ninguna

**Descripción**:
Audit log completo de acciones de AI

**Tareas**:

- [ ] Log de cada scan con resultados
- [ ] Log de sugerencias aplicadas automáticamente
- [ ] Log de deletion requests con reasoning
- [ ] Retention configurable (default: 90 días)
- [ ] API para consultar audit log
- [ ] Exportación de audit log

**Archivos a Modificar**:

- `src/documents/ai_scanner.py`
- `src/documents/ai_deletion_manager.py`

**Criterios de Aceptación**:

- Audit trail completo y consultable
- Cumple con requisitos de auditoría

---

## 📊 ÉPICA 8: Documentación de Usuario

### Issue 8.1: Guía de Usuario para AI Features

**Prioridad**: 🔴 ALTA
**Estimación**: 2-3 días
**Dependencias**: Issue 4.1, 4.2

**Descripción**:
Documentación completa para usuarios finales

**Tareas**:

- [ ] Guía: "Cómo funciona el AI Scanner"
- [ ] Guía: "Entendiendo las sugerencias de AI"
- [ ] Guía: "Gestión de Deletion Requests"
- [ ] Guía: "Configuración de AI"
- [ ] FAQ sobre AI features
- [ ] Screenshots de UI
- [ ] Videos tutorial (opcional)

**Archivos a Crear**:

- `docs/ai-scanner-user-guide.md`
- `docs/ai-deletion-requests.md`
- `docs/ai-configuration.md`
- `docs/ai-faq.md`

**Criterios de Aceptación**:

- Documentación clara y con ejemplos
- Screenshots actualizados
- Traducida a español e inglés

---

### Issue 8.2: API Documentation

**Prioridad**: 🟡 MEDIA
**Estimación**: 1-2 días
**Dependencias**: Issue 3.1, 3.2, 3.3

**Descripción**:
Documentación de API REST completa

**Tareas**:

- [ ] Swagger/OpenAPI spec completo
- [ ] Ejemplos de requests/responses
- [ ] Guía de autenticación
- [ ] Rate limits documentados
- [ ] Error codes documentados
- [ ] Postman collection

**Archivos a Crear**:

- `docs/api/ai-scanner-api.md`
- `postman/ai-scanner.json`

**Criterios de Aceptación**:

- API completamente documentada
- Ejemplos funcionan
- Postman collection testeada

---

### Issue 8.3: Guía de Administrador

**Prioridad**: 🟡 MEDIA
**Estimación**: 2 días
**Dependencias**: Issue 8.1

**Descripción**:
Documentación para administradores del sistema

**Tareas**:

- [ ] Guía de instalación y configuración
- [ ] Guía de troubleshooting
- [ ] Guía de optimización de performance
- [ ] Guía de training de modelos custom
- [ ] Guía de monitoreo y métricas
- [ ] Best practices

**Archivos a Crear**:

- `docs/admin/ai-scanner-setup.md`
- `docs/admin/ai-scanner-troubleshooting.md`
- `docs/admin/ai-scanner-optimization.md`

**Criterios de Aceptación**:

- Admin puede configurar sistema completamente
- Troubleshooting cubre casos comunes

---

## 📊 ÉPICA 9: Seguridad Avanzada

### Issue 9.1: Rate Limiting para AI Operations

**Prioridad**: 🟡 MEDIA
**Estimación**: 1-2 días
**Dependencias**: Ninguna

**Descripción**:
Implementar rate limiting para prevenir abuso

**Tareas**:

- [ ] Rate limit por usuario: X scans/hora
- [ ] Rate limit global: Y scans/minuto
- [ ] Rate limit para deletion requests: Z requests/día
- [ ] Bypass para admin/superuser
- [ ] Mensajes de error claros cuando se exceed
- [ ] Métricas de rate limiting

**Archivos a Modificar**:

- `src/documents/views/*.py`
- Middleware de rate limiting

**Criterios de Aceptación**:

- No se puede abusar del sistema
- Límites configurables
- Admin puede ver quién está rate limited

---

### Issue 9.2: Validation de Inputs

**Prioridad**: 🔴 ALTA
**Estimación**: 1 día
**Dependencias**: Ninguna

**Descripción**:
Validación exhaustiva de inputs para prevenir inyección

**Tareas**:

- [ ] Validar todas las entradas de usuario
- [ ] Sanitizar strings antes de procesamiento ML
- [ ] Validar confianza en rango [0.0, 1.0]
- [ ] Validar IDs de documentos
- [ ] Prevenir path traversal en file paths
- [ ] Tests de seguridad

**Archivos a Modificar**:

- `src/documents/ai_scanner.py`
- `src/documents/ai_deletion_manager.py`

**Criterios de Aceptación**:

- Inputs validados exhaustivamente
- Tests de seguridad pasan

---

### Issue 9.3: Permissions Granulares

**Prioridad**: 🟡 MEDIA
**Estimación**: 2 días
**Dependencias**: Issue 3.1

**Descripción**:
Sistema de permisos granular para AI features

**Tareas**:

- [ ] Permiso: `can_view_ai_suggestions`
- [ ] Permiso: `can_apply_ai_suggestions`
- [ ] Permiso: `can_approve_deletions`
- [ ] Permiso: `can_configure_ai`
- [ ] Role-based access control
- [ ] Tests de permisos

**Archivos a Modificar**:

- `src/documents/permissions.py`
- `src/documents/views/*.py`

**Criterios de Aceptación**:

- Permisos granulares funcionales
- Admin puede asignar permisos
- Tests verifican permisos

---

## 📊 ÉPICA 10: Internacionalización

### Issue 10.1: Traducción de Mensajes de AI

**Prioridad**: 🟢 BAJA
**Estimación**: 1-2 días
**Dependencias**: Ninguna

**Descripción**:
Internacionalizar todos los mensajes de AI

**Tareas**:

- [ ] Marcar strings para traducción con gettext
- [ ] Traducir a español
- [ ] Traducir a inglés
- [ ] Traducir mensajes de deletion requests
- [ ] Traducir labels de UI
- [ ] Tests con diferentes locales

**Archivos a Modificar**:

- `src/documents/ai_scanner.py`
- `src/documents/ai_deletion_manager.py`
- Archivos de traducción

**Criterios de Aceptación**:

- Todos los mensajes traducidos
- UI cambia según locale
- Tests pasan en ambos idiomas

---

## 📅 Roadmap Propuesto

### Sprint 1 (2 semanas) - Fundamentos

- Issue 1.1: Tests Unitarios AI Scanner
- Issue 1.2: Tests Unitarios AI Deletion Manager
- Issue 1.3: Tests de Integración Consumer
- Issue 2.1: Migración DeletionRequest

### Sprint 2 (2 semanas) - API

- Issue 3.1: API Endpoints Deletion Requests - Listado
- Issue 3.2: API Endpoints Deletion Requests - Acciones
- Issue 3.3: API Endpoints AI Suggestions

### Sprint 3 (2 semanas) - Frontend

- Issue 4.1: UI AI Suggestions
- Issue 4.2: UI Deletion Requests
- Issue 4.3: AI Status Indicator

### Sprint 4 (2 semanas) - Performance

- Issue 5.1: Caching Modelos ML
- Issue 5.2: Procesamiento Asíncrono
- Issue 7.1: Metrics y Logging

### Sprint 5 (2 semanas) - Documentación y Refinamiento

- Issue 8.1: Guía de Usuario
- Issue 8.2: API Documentation
- Issue 1.4: Linting
- Issue 9.2: Validation

### Sprint 6 (2 semanas) - ML Improvements

- Issue 6.1: Training Pipeline
- Issue 6.3: Multi-language Support
- Issue 6.4: Confidence Calibration

---

## 📊 Priorización

### 🔴 ALTA Prioridad (Hacer primero)

1. Tests (Issues 1.1, 1.2, 1.3)
2. Migración DB (Issue 2.1)
3. API básica (Issues 3.1, 3.2)
4. UI básica (Issues 4.1, 4.2)
5. Documentación usuario (Issue 8.1)
6. Seguridad (Issue 9.2)

### 🟡 MEDIA Prioridad (Hacer después)

7. Optimización (Issues 5.1, 5.2, 5.3, 5.4)
8. API avanzada (Issue 3.3)
9. ML improvements (Issues 6.3, 6.4)
10. Monitoreo (Issues 7.1, 7.2, 7.3)
11. Seguridad avanzada (Issues 9.1, 9.3)

### 🟢 BAJA Prioridad (Nice to have)

12. Webhooks (Issue 3.4)
13. Active Learning (Issue 6.2)
14. i18n (Issue 10.1)
15. Guías avanzadas (Issues 8.3)

---

## 📈 Métricas de Éxito

### Cobertura de Tests

- Target: >90% para código crítico
- Target: >80% para código general

### Performance

- AI Scan time: <2s por documento
- API response time: <200ms
- UI load time: <1s

### Calidad

- Zero linting errors
- Zero security vulnerabilities
- API uptime: >99.9%

### User Satisfaction

- User feedback: >4.5/5
- AI suggestion acceptance rate: >70%
- Deletion request false positive rate: <5%

---

## 🎯 Conclusión

Este plan de mejoras cubre todos los aspects necesarios para llevar el AI Scanner de PRODUCTION READY a PRODUCTION EXCELLENCE. La implementación de estos issues transformará el sistema en una solución robusta, escalable y amigable para el usuario.

**Total Estimado**: ~60-80 días de desarrollo (3-4 meses con 1 desarrollador)

**Épicas**: 10
**Issues**: 35+
**Prioridad Alta**: 8 issues
**Prioridad Media**: 18 issues
**Prioridad Baja**: 9 issues
