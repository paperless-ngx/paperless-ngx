# GitHub Issues Templates para AI Scanner

Este documento contiene todos los issues que deben crearse para las mejoras del AI Scanner. Cada issue está formateado para set copiado directamente a GitHub.

---

## 📊 ÉPICA 1: Testing y Calidad de Código

### Issue 1.1: [AI Scanner] Tests Unitarios para AI Scanner

**Labels**: `testing`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] Cobertura de código >90% para ai_scanner.py
- [ ] Todos los tests pasan en CI/CD
- [ ] Tests incluyen casos edge y errores

**Estimación**: 3-5 días
**Prioridad**: 🔴 ALTA
**Épica**: Testing y Calidad de Código

---

### Issue 1.2: [AI Scanner] Tests Unitarios para AI Deletion Manager

**Labels**: `testing`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] Cobertura >95% para components críticos de seguridad
- [ ] Tests verifican constraints de seguridad
- [ ] Tests pasan en CI/CD

**Estimación**: 2-3 días
**Prioridad**: 🔴 ALTA
**Épica**: Testing y Calidad de Código

---

### Issue 1.3: [AI Scanner] Tests de Integración para Consumer

**Labels**: `testing`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] Pipeline completo testeado end-to-end
- [ ] Graceful degradation verificado
- [ ] Performance acceptable (<2s adicionales por documento)

**Estimación**: 2-3 días
**Prioridad**: 🔴 ALTA
**Dependencias**: Issue 1.1
**Épica**: Testing y Calidad de Código

---

### Issue 1.4: [AI Scanner] Pre-commit Hooks y Linting

**Labels**: `code-quality`, `priority-medium`, `ai-scanner`, `enhancement`

**Descripción**:

Ejecutar y corregir linters en código nuevo del AI Scanner

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
- [ ] Cero warnings de linters
- [ ] Código pasa pre-commit hooks
- [ ] Type hints completos

**Estimación**: 1 día
**Prioridad**: 🟡 MEDIA
**Épica**: Testing y Calidad de Código

---

## 📊 ÉPICA 2: Migraciones de Base de Datos

### Issue 2.1: [AI Scanner] Migración Django para DeletionRequest

**Labels**: `database`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] Migración se ejecuta sin errores
- [ ] Índices creados correctamente
- [ ] Backward compatible si possible

**Estimación**: 1 día
**Prioridad**: 🔴 ALTA
**Dependencias**: Issue 1.2
**Épica**: Migraciones de Base de Datos

---

### Issue 2.2: [AI Scanner] Índices de Performance para DeletionRequest

**Labels**: `database`, `performance`, `priority-medium`, `ai-scanner`, `enhancement`

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
- [ ] Queries de listado <100ms
- [ ] Queries de filtrado <50ms

**Estimación**: 0.5 días
**Prioridad**: 🟡 MEDIA
**Dependencias**: Issue 2.1
**Épica**: Migraciones de Base de Datos

---

## 📊 ÉPICA 3: API REST Endpoints

### Issue 3.1: [AI Scanner] API Endpoints para Deletion Requests - Listado y Detalle

**Labels**: `api`, `priority-high`, `ai-scanner`, `enhancement`

**Descripción**:

Crear endpoints REST para gestión de deletion requests (listado y detalle)

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
- [ ] Endpoints documentados en Swagger
- [ ] Tests de API incluidos
- [ ] Permisos verificados (solo requests propios o admin)

**Estimación**: 2-3 días
**Prioridad**: 🔴 ALTA
**Dependencias**: Issue 2.1
**Épica**: API REST Endpoints

---

### Issue 3.2: [AI Scanner] API Endpoints para Deletion Requests - Acciones

**Labels**: `api`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] Workflow completo functional via API
- [ ] Validaciones de estado y permisos
- [ ] Tests de API incluidos

**Estimación**: 2 días
**Prioridad**: 🔴 ALTA
**Dependencias**: Issue 3.1
**Épica**: API REST Endpoints

---

### Issue 3.3: [AI Scanner] API Endpoints para AI Suggestions

**Labels**: `api`, `priority-medium`, `ai-scanner`, `enhancement`

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
- [ ] Frontend puede obtener y aplicar sugerencias
- [ ] Tracking de user feedback
- [ ] API documentada

**Estimación**: 2-3 días
**Prioridad**: 🟡 MEDIA
**Épica**: API REST Endpoints

---

### Issue 3.4: [AI Scanner] Webhooks para Eventos de AI

**Labels**: `api`, `webhooks`, `priority-low`, `ai-scanner`, `enhancement`

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
- [ ] Webhooks configurables
- [ ] Retry logic robusto
- [ ] Eventos documentados

**Estimación**: 2 días
**Prioridad**: 🟢 BAJA
**Dependencias**: Issues 3.1, 3.3
**Épica**: API REST Endpoints

---

## 📊 ÉPICA 4: Integración Frontend

### Issue 4.1: [AI Scanner] UI para AI Suggestions en Document Detail

**Labels**: `frontend`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] UI intuitiva y atractiva
- [ ] Mobile responsive
- [ ] Tests de componente incluidos

**Estimación**: 3-4 días
**Prioridad**: 🔴 ALTA
**Dependencias**: Issue 3.3
**Épica**: Integración Frontend

---

### Issue 4.2: [AI Scanner] UI para Deletion Requests Management

**Labels**: `frontend`, `priority-high`, `ai-scanner`, `enhancement`

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
- [ ] Usuario puede revisar y aprobar/rechazar requests
- [ ] Análisis de impacto claro y comprensible
- [ ] Notificaciones visuals

**Estimación**: 3-4 días
**Prioridad**: 🔴 ALTA
**Dependencias**: Issues 3.1, 3.2
**Épica**: Integración Frontend

---

### Issue 4.3: [AI Scanner] AI Status Indicator

**Labels**: `frontend`, `priority-medium`, `ai-scanner`, `enhancement`

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
- [ ] Estado de AI siempre visible
- [ ] Notificaciones no intrusivas

**Estimación**: 1-2 días
**Prioridad**: 🟡 MEDIA
**Épica**: Integración Frontend

---

### Issue 4.4: [AI Scanner] Settings Page para AI Configuration

**Labels**: `frontend`, `priority-medium`, `ai-scanner`, `enhancement`

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
- [ ] Configuración intuitiva y clara
- [ ] Cambios se reflejan inmediatamente
- [ ] Validación de valores

**Estimación**: 2-3 días
**Prioridad**: 🟡 MEDIA
**Épica**: Integración Frontend

---

## 📊 ÉPICAS RESTANTES (5-10)

Ver `AI_SCANNER_IMPROVEMENT_PLAN.md` para detalles completos de:

- **ÉPICA 5**: Optimización de Performance (4 issues)
- **ÉPICA 6**: Mejoras de ML/AI (4 issues)
- **ÉPICA 7**: Monitoreo y Observabilidad (3 issues)
- **ÉPICA 8**: Documentación de Usuario (3 issues)
- **ÉPICA 9**: Seguridad Avanzada (3 issues)
- **ÉPICA 10**: Internacionalización (1 issue)

**Total estimado**: 35+ issues

---

## 📋 Instrucciones de Creación

1. Ve a https://github.com/dawnsystem/IntelliDocs-ngx/issues/new
2. Copia el contenido de cada issue de arriba
3. Pega en el formulario de nuevo issue
4. Añade los labels correspondientes
5. Crea el issue
6. Repite para cada issue

O usa GitHub CLI:
```bash
# Asegúrate de tener autenticación configurada
gh auth login

# Luego crea issues con:
gh issue create --title "Título" --body "Descripción" --label "label1,label2"
```

---

## 📊 Resumen de Prioridades

### 🔴 ALTA (14 issues)
- Épica 1: 3 issues (tests)
- Épica 2: 1 issue (migración)
- Épica 3: 2 issues (API básica)
- Épica 4: 2 issues (UI básica)
- Épica 8: 1 issue (docs usuario)
- Épica 9: 1 issue (seguridad)

### 🟡 MEDIA (18 issues)
- Épica 1: 1 issue
- Épica 2: 1 issue
- Épica 3: 1 issue
- Épica 4: 2 issues
- Épica 5: 4 issues (performance)
- Épica 6: 3 issues (ML)
- Épica 7: 3 issues (monitoreo)
- Épica 9: 2 issues (seguridad)

### 🟢 BAJA (9 issues)
- Épica 3: 1 issue
- Épica 6: 1 issue
- Épica 8: 2 issues
- Épica 10: 1 issue

**Total: 35+ issues**
