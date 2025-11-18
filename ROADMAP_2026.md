# 🗺️ IntelliDocs-ngx - Hoja de Ruta 2026 (Roadmap Annual)

**Versión:** 1.0
**Fecha de Creación:** 2025-11-09
**Última Actualización:** 2025-11-09 22:39:23 UTC
**Autoridad:** Este documento sigue las directivas de `agents.md`
**Estado:** 🟢 ACTIVO

---

## 📋 Resumen Ejecutivo

Esta hoja de ruta define **todas las implementaciones planificadas para IntelliDocs-ngx durante el año 2026**, organizadas en **12 Epics principales** distribuidas en **4 trimestres**. El plan incluye:

- **145 tareas específicas** distribuidas en 12 meses
- **Modelo:** Proyecto Open Source con contribuciones de la comunidad
- **Enfoque:** Usuarios individuales y PYMEs (pequeñas/medianas empresas)
- **Costo real:** $0 USD/año (100% gratuito - proyecto Open Source sin servicios de pago)

### 🎯 Objetivos Estratégicos 2026

**Enfoque:** Usuarios individuales y pequeñas/medianas empresas (PYMEs)

1. **Consolidación y Calidad** (Q1-Q2): Optimizar base actual, resolver deuda técnica, mejorar experiencia de usuario
2. **Accesibilidad** (Q2-Q3): Mobile app, sincronización simple, mejor UI/UX
3. **Colaboración Básica** (Q3-Q4): Compartir documentos, permisos simples, trabajo en equipo pequeño
4. **Refinamiento** (Q4): Pulir features existentes, documentación de usuario, estabilidad

---

## 📊 Vista General por Trimestre

| Trimestre   | Epics Principales            | Tareas         | Esfuerzo       | Prioridad                                |
| ----------- | ---------------------------- | -------------- | -------------- | ---------------------------------------- |
| **Q1 2026** | Consolidación Base + Testing | 42             | 13 semanas     | 🔴 Alta                                  |
| **Q2 2026** | Mobile + Cloud Sync          | 51             | 13 semanas     | 🟡 Media-Alta                            |
| **Q3 2026** | Colaboración + UX Simple     | 40             | 13 semanas     | 🟡 Media                                 |
| **Q4 2026** | Documentación + Refinamiento | 12             | 13 semanas     | 🟢 Media                                 |
| **Total**   | **12 Epics**                 | **145 tareas** | **52 semanas** | Enfoque en usuarios individuales y PYMEs |

---

## 🎯 EPIC 1: Testing y QA Completo (Q1 2026)

**Prioridad:** 🔴 CRÍTICA
**Duración:** 4 semanas
**Dependencias:** Ninguna (Fase 0)
**Objetivo:** Cobertura >90% de código para validar las 4 fases implementadas

### Tareas (12 total)

#### 1.1 Tests Unitarios - Módulo ML/IA

- [ ] **TSK-2601:** Tests para `classifier.py` (clasificación BERT)

  - Subtareas: test_train_model, test_predict, test_save_load, test_edge_cases
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2602:** Tests para `ner.py` (Named Entity Recognition)

  - Subtareas: test_extract_entities, test_invoice_data, test_confidence_scores
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2603:** Tests para `semantic_search.py`
  - Subtareas: test_index_document, test_search, test_similarity_scoring
  - Estimación: 1.5 días
  - Prioridad: Alta

#### 1.2 Tests Unitarios - Módulo OCR Avanzado

- [ ] **TSK-2604:** Tests para `table_extractor.py`

  - Subtareas: test_detect_tables, test_extract_data, test_accuracy_benchmark
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2605:** Tests para `handwriting.py`

  - Subtareas: test_recognize_handwriting, test_trocr_model, test_fallback_tesseract
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2606:** Tests para `form_detector.py`
  - Subtareas: test_detect_forms, test_extract_fields, test_checkbox_detection
  - Estimación: 2 días
  - Prioridad: Alta

#### 1.3 Tests de Integración - Seguridad

- [ ] **TSK-2607:** Tests de integración para `middleware.py` (rate limiting)

  - Subtareas: test_rate_limits, test_ip_detection, test_user_limits
  - Estimación: 1.5 días
  - Prioridad: Alta

- [ ] **TSK-2608:** Tests para `security.py` (validación de archivos)
  - Subtareas: test_mime_validation, test_malware_detection, test_content_scan
  - Estimación: 2 días
  - Prioridad: Crítica

#### 1.4 Tests de Performance

- [ ] **TSK-2609:** Benchmark de índices de BD

  - Subtareas: measure_query_times, compare_before_after, stress_test
  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2610:** Benchmark de sistema de caché
  - Subtareas: test_cache_hit_rate, test_invalidation, load_test
  - Estimación: 1 día
  - Prioridad: Media

#### 1.5 Tests E2E (End-to-End)

- [ ] **TSK-2611:** Tests E2E - Flujo completo de upload + OCR + clasificación

  - Subtareas: setup_test_env, test_pdf_upload, test_ocr_execution, test_auto_classify
  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2612:** Tests E2E - Búsqueda semántica + filtros
  - Subtareas: test_semantic_search, test_combined_filters, test_performance
  - Estimación: 2 días
  - Prioridad: Media

### Métricas de Éxito

- ✅ Cobertura de código: >90% líneas, >85% ramas
- ✅ Todos los tests passing en CI/CD
- ✅ Documentación de tests completa

---

## 🎯 EPIC 2: Documentación API y Swagger (Q1 2026)

**Prioridad:** 🔴 ALTA
**Duración:** 2 semanas
**Dependencias:** EPIC 1
**Objetivo:** API totalmente documentada con OpenAPI 3.0

### Tareas (8 total)

- [ ] **TSK-2613:** Configurar drf-spectacular para generación automática

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2614:** Documentar endpoints de documentos (CRUD + búsqueda)

  - Subtareas: schemas, ejemplos, responses, error_codes
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2615:** Documentar endpoints de ML/IA (clasificación, NER, semantic search)

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2616:** Documentar endpoints de OCR (table extraction, handwriting)

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2617:** Documentar endpoints de autenticación y seguridad

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2618:** Crear ejemplos interactivos en Swagger UI

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2619:** Generar cliente SDK en Python y TypeScript

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2620:** Documentación de rate limits y cuotas
  - Estimación: 0.5 días
  - Prioridad: Media

### Entregables

- 📄 Swagger UI público en `/api/docs/`
- 📦 SDK clients (Python, TypeScript)
- 📖 Guía de uso de API

---

## 🎯 EPIC 3: Optimización Avanzada de Performance (Q1 2026)

**Prioridad:** 🟡 MEDIA-ALTA
**Duración:** 3 semanas
**Dependencias:** EPIC 1 (para validar mejoras)
**Objetivo:** Reducir tiempos de respuesta en 50% adicional

### Tareas (10 total)

#### 3.1 Optimización Frontend

- [ ] **TSK-2621:** Implementar lazy loading avanzado en Angular

  - Subtareas: route_lazy_loading, component_lazy_loading, module_preloading
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2622:** Virtual scrolling para listas de documentos

  - Estimación: 1.5 días
  - Prioridad: Alta

- [ ] **TSK-2623:** Optimización de imágenes (WebP, lazy loading)

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2624:** Service Workers para caché offline
  - Estimación: 2 días
  - Prioridad: Media

#### 3.2 Optimización Backend

- [ ] **TSK-2625:** Implementar GraphQL como alternativa a REST

  - Subtareas: setup_graphene, create_schemas, optimize_resolvers
  - Estimación: 5 días
  - Prioridad: Media

- [ ] **TSK-2626:** Query batching y DataLoader pattern

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2627:** Celery para procesamiento asíncrono pesado (OCR, ML)

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2628:** Optimización de serializers (select_related, prefetch_related)
  - Estimación: 1.5 días
  - Prioridad: Media

#### 3.3 Monitoreo

- [ ] **TSK-2629:** Implementar APM (Application Performance Monitoring) con Sentry

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2630:** Dashboard de métricas en Grafana + Prometheus
  - Estimación: 2 días
  - Prioridad: Media

### KPIs

- 📉 Tiempo de carga inicial: <2s (actualmente ~3-4s)
- 📉 API response time p95: <200ms
- 📈 Throughput: +50% requests/second

---

## 🎯 EPIC 4: Encriptación de Documentos en Reposo (Q1 2026)

**Prioridad:** 🔴 CRÍTICA (Security)
**Duración:** 3 semanas
**Dependencias:** EPIC 1 (tests de seguridad)
**Objetivo:** Proteger documentos con encriptación AES-256

### Tareas (12 total)

- [ ] **TSK-2631:** Diseño de arquitectura de encriptación

  - Subtareas: key_management_design, rotation_strategy, backup_strategy
  - Estimación: 2 días
  - Prioridad: Crítica

- [ ] **TSK-2632:** Implementar módulo de encriptación con Fernet (cryptography)

  - Estimación: 2 días
  - Prioridad: Crítica

- [ ] **TSK-2633:** Integrar encriptación en Consumer (pipeline de ingesta)

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2634:** Implementar desencriptación transparente al servir documentos

  - Estimación: 1.5 días
  - Prioridad: Alta

- [ ] **TSK-2635:** Sistema de gestión de claves (KMS)

  - Subtareas: vault_integration, key_rotation, audit_logging
  - Estimación: 4 días
  - Prioridad: Crítica

- [ ] **TSK-2636:** Commando de migración: encriptar documentos existentes

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2637:** Tests de seguridad para encriptación

  - Estimación: 2 días
  - Prioridad: Crítica

- [ ] **TSK-2638:** Documentación de configuración de encriptación

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2639:** Implementar key rotation automática

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2640:** Backup seguro de claves de encriptación

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2641:** Compliance check (GDPR, HIPAA)

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2642:** Performance benchmark con encriptación habilitada
  - Estimación: 0.5 días
  - Prioridad: Media

### Entregables

- 🔐 Encriptación AES-256 para todos los documentos
- 🔑 KMS integrado (HashiCorp Vault o AWS KMS)
- 📋 Compliance report (GDPR, HIPAA ready)

---

## 🎯 EPIC 5: Aplicación Móvil Nativa (Q2 2026)

**Prioridad:** 🟡 MEDIA-ALTA
**Duración:** 8 semanas
**Dependencias:** EPIC 2 (API documentada)
**Objetivo:** Apps iOS y Android con React Native

### Tareas (28 total)

#### 5.1 Setup y Arquitectura

- [ ] **TSK-2643:** Setup inicial de React Native con TypeScript

  - Estimación: 1 día
  - Prioridad: Alta

- [ ] **TSK-2644:** Arquitectura de la app (Redux/MobX, navegación)

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2645:** Configuración de CI/CD para mobile (Fastlane)
  - Estimación: 2 días
  - Prioridad: Media

#### 5.2 Features Core

- [ ] **TSK-2646:** Autenticación (login, biométrico)

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2647:** Lista de documentos con infinite scroll

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2648:** Visor de documentos PDF

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2649:** Búsqueda de documentos (full-text + semántica)

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2650:** Filtros avanzados (tags, correspondientes, fechas)
  - Estimación: 2 días
  - Prioridad: Media

#### 5.3 Document Scanner

- [ ] **TSK-2651:** Integrar camera API para captura

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2652:** Detección automática de bordes del documento

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2653:** Corrección de perspectiva y mejora de imagen

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2654:** Upload directo con progress indicator

  - Estimación: 1.5 días
  - Prioridad: Alta

- [ ] **TSK-2655:** Soporte para multi-página (escaneo por lotes)
  - Estimación: 2 días
  - Prioridad: Media

#### 5.4 Offline Mode

- [ ] **TSK-2656:** Implementar caché local con AsyncStorage

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2657:** Queue de uploads offline

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2658:** Sincronización automática al recuperar conexión
  - Estimación: 2 días
  - Prioridad: Alta

#### 5.5 Notificaciones

- [ ] **TSK-2659:** Push notifications (Firebase/OneSignal)

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2660:** Notificaciones de nuevos documentos compartidos
  - Estimación: 1 día
  - Prioridad: Baja

#### 5.6 Testing y Deployment

- [ ] **TSK-2661:** Tests unitarios para components críticos

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2662:** Tests E2E con Detox

  - Estimación: 3 días
  - Prioridad: Media

- [ ] **TSK-2663:** Beta testing con usuarios (distribución directa APK)

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2664:** Publicación en F-Droid (Android open source store)

  - Subtareas: fdroid_metadata, prepare_release, submit
  - Estimación: 2 días
  - Prioridad: Alta
  - ✅ **GRATIS** - F-Droid no cobra por publicar

- [ ] **TSK-2665:** Setup de distribución directa APK (GitHub Releases)

  - Estimación: 1 día
  - Prioridad: Alta
  - ✅ **GRATIS** - sin costo de stores

- [ ] **TSK-2666:** Documentación de instalación manual (sideloading)
  - Estimación: 1 día
  - Prioridad: Media

#### 5.7 Features Adicionales

- [ ] **TSK-2667:** Compartir documentos (share sheet nativo)

  - Estimación: 1 día
  - Prioridad: Baja

- [ ] **TSK-2668:** Favoritos y listas personalizadas

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2669:** Modo oscuro

  - Estimación: 1 día
  - Prioridad: Baja

- [ ] **TSK-2670:** Widgets para iOS/Android
  - Estimación: 3 días
  - Prioridad: Baja

### KPIs

- 📱 Soporte iOS 14+ y Android 10+
- ⭐ Rating objetivo: >4.5 estrellas
- 📊 Crash-free rate: >99.5%

---

## 🎯 EPIC 6: Cloud Storage Sync (Q2 2026)

**Prioridad:** 🟡 MEDIA
**Duración:** 4 semanas
**Dependencias:** EPIC 2
**Objetivo:** Sincronización bidireccional con Dropbox, Google Drive, OneDrive

### Tareas (15 total)

#### 6.1 Arquitectura de Sync

- [ ] **TSK-2671:** Diseño de sistema de sincronización

  - Subtareas: conflict_resolution, deduplication, incremental_sync
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2672:** Modelo de datos para tracking de sync
  - Estimación: 1 día
  - Prioridad: Alta

#### 6.2 Dropbox Integration

- [ ] **TSK-2673:** OAuth flow para Dropbox

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2674:** Implementar sync bidireccional con Dropbox SDK

  - Subtareas: upload, download, delete, webhooks
  - Estimación: 4 días
  - Prioridad: Media

- [ ] **TSK-2675:** Manejo de conflictos (versioning)
  - Estimación: 2 días
  - Prioridad: Media

#### 6.3 Google Drive Integration

- [ ] **TSK-2676:** OAuth flow para Google Drive

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2677:** Implementar sync con Google Drive API

  - Estimación: 4 días
  - Prioridad: Media

- [ ] **TSK-2678:** Manejo de permisos y carpetas compartidas
  - Estimación: 2 días
  - Prioridad: Baja

#### 6.4 OneDrive Integration

- [ ] **TSK-2679:** OAuth flow para OneDrive (Microsoft Graph)

  - Estimación: 1 día
  - Prioridad: Baja

- [ ] **TSK-2680:** Implementar sync con Microsoft Graph API
  - Estimación: 4 días
  - Prioridad: Baja

#### 6.5 Features Comunes

- [ ] **TSK-2681:** Panel de configuración de sync en UI

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2682:** Monitor de estado de sync (logs, errores)

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2683:** Resolución de conflictos manual (UI)

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2684:** Tests de integración para cada proveedor

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2685:** Documentación de configuración de cloud sync
  - Estimación: 1 día
  - Prioridad: Media

### Entregables

- ☁️ Sync con 3 proveedores cloud principales
- 🔄 Sincronización bidireccional automática
- ⚔️ Sistema de resolución de conflictos

---

## 🎯 EPIC 7: Estadísticas Básicas y Reportes (Q2 2026)

**Prioridad:** 🟡 MEDIA
**Duración:** 2 semanas
**Dependencias:** EPIC 1, EPIC 3
**Objetivo:** Dashboard simple con estadísticas de uso personal

### Tareas (8 total)

#### 7.1 Estadísticas Básicas

- [ ] **TSK-2686:** Vista de estadísticas personales

  - Subtareas: total_docs, storage_used, recent_activity
  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2687:** Gráfico de documentos por mes

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2688:** Desglose por tags y tipos de documentos

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2689:** Búsquedas más frecuentes
  - Estimación: 1 día
  - Prioridad: Baja

#### 7.2 Reportes Simples

- [ ] **TSK-2690:** Export de lista de documentos (CSV)

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2691:** Resumen mensual por email (opcional)

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2692:** Reporte de espacio usado

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2693:** Tests para módulo de estadísticas
  - Estimación: 1 día
  - Prioridad: Media

### Entregables

- 📊 Dashboard personal con estadísticas básicas
- 📈 Gráficos simples de uso
- 📄 Export de listas (CSV)

---

## 🎯 EPIC 8: Colaboración y Anotaciones (Q3 2026)

**Prioridad:** 🟡 MEDIA
**Duración:** 4 semanas
**Dependencias:** EPIC 2
**Objetivo:** Features de colaboración en tiempo real

### Tareas (16 total)

#### 8.1 Comentarios y Discusiones

- [ ] **TSK-2699:** Modelo de datos para comentarios

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2700:** API de comentarios (CRUD + threading)

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2701:** UI de comentarios en visor de documentos

  - Estimación: 3 días
  - Prioridad: Media

- [ ] **TSK-2702:** Menciones de usuarios (@usuario)

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2703:** Notificaciones de comentarios
  - Estimación: 1 día
  - Prioridad: Media

#### 8.2 Anotaciones Visuals

- [ ] **TSK-2704:** Modelo para anotaciones (highlights, rectangles, arrows)

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2705:** Canvas de anotación en PDF viewer

  - Subtareas: drawing_tools, color_picker, undo_redo
  - Estimación: 5 días
  - Prioridad: Media

- [ ] **TSK-2706:** Persistencia de anotaciones en backend

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2707:** Export de PDF con anotaciones incluidas
  - Estimación: 2 días
  - Prioridad: Baja

#### 8.3 Colaboración en Tiempo Real

- [ ] **TSK-2708:** WebSockets con Django Channels

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2709:** Presencia de usuarios (quién está viendo el documento)

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2710:** Cursores colaborativos (estilo Google Docs)
  - Estimación: 3 días
  - Prioridad: Baja

#### 8.4 Compartir y Permisos

- [ ] **TSK-2711:** Sistema de permisos granulares (read, write, annotate, share)

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2712:** Links de compartir con expiración

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2713:** Compartir con usuarios externos (sin cuenta)

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2714:** Tests de colaboración
  - Estimación: 2 días
  - Prioridad: Media

### Entregables

- 💬 Sistema de comentarios threaded
- 🎨 Herramientas de anotación visual
- 👥 Colaboración en tiempo real (WebSockets)

---

## 🎯 EPIC 9: Mejoras de UX y Experiencia de Usuario (Q3 2026)

**Prioridad:** 🟡 MEDIA
**Duración:** 3 semanas
**Dependencias:** EPIC 8 (colaboración)
**Objetivo:** Hacer la app más intuitiva y fácil de usar para usuarios finales

### Tareas (12 total)

#### 9.1 Interfaz de Usuario Mejorada

- [ ] **TSK-2715:** Rediseño del dashboard principal

  - Subtareas: wireframes, user_research, implementation
  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2716:** Onboarding interactivo para nuevos usuarios

  - Subtareas: tutorial_steps, tooltips, help_bubbles
  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2717:** Búsqueda mejorada con sugerencias

  - Subtareas: autocomplete, recent_searches, saved_searches
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2718:** Accesos directos de teclado
  - Subtareas: shortcut_mapping, help_modal, customization
  - Estimación: 1.5 días
  - Prioridad: Media

#### 9.2 Accesibilidad

- [ ] **TSK-2719:** Soporte de modo oscuro completo

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2720:** Soporte ARIA para lectores de pantalla

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2721:** Tamaño de fuente ajustable
  - Estimación: 1 día
  - Prioridad: Baja

#### 9.3 Personalización

- [ ] **TSK-2722:** Temas personalizables (colores)

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2723:** Vista de documentos configurable (lista/grid/cards)

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2724:** Preferencias de usuario guardadas
  - Estimación: 1 día
  - Prioridad: Media

#### 9.4 Performance UI

- [ ] **TSK-2725:** Skeleton screens para mejor perceived performance

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2726:** Tests de usabilidad con usuarios reales
  - Estimación: 2 días
  - Prioridad: Alta

### Entregables

- 🎨 Interfaz renovada y más intuitiva
- ♿ Accesibilidad mejorada
- 🎨 Personalización para usuarios
- 📊 Métricas de usabilidad

---

## 🎯 EPIC 10: Compartir y Permisos Simples (Q3-Q4 2026)

**Prioridad:** 🟡 MEDIA
**Duración:** 3 semanas
**Dependencias:** EPIC 8 (colaboración)
**Objetivo:** Permitir compartir documentos fácilmente con familia, amigos, o equipos pequeños

### Tareas (12 total)

#### 10.1 Sistema de Compartir

- [ ] **TSK-2727:** Links públicos con expiración

  - Subtareas: generate_link, expiration_dates, password_protection
  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2728:** Compartir por email

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2729:** Compartir múltiples documentos (carpetas)

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2730:** Revocar accesos compartidos
  - Estimación: 1 día
  - Prioridad: Alta

#### 10.2 Permisos Básicos

- [ ] **TSK-2731:** Permisos simples (ver/editar/descargar)

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2732:** Usuarios invitados (sin cuenta)

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2733:** Grupos simples para familias/equipos pequeños
  - Estimación: 2 días
  - Prioridad: Media

#### 10.3 Notificaciones

- [ ] **TSK-2734:** Notificaciones de documentos compartidos

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2735:** Historical de accesos (quién vio qué)
  - Estimación: 2 días
  - Prioridad: Baja

#### 10.4 Seguridad

- [ ] **TSK-2736:** Watermarks en documentos compartidos (opcional)

  - Estimación: 2 días
  - Prioridad: Baja

- [ ] **TSK-2737:** Logs de actividad de compartidos

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2738:** Tests de seguridad para compartir
  - Estimación: 2 días
  - Prioridad: Alta

### Entregables

- 🔗 Sistema simple de compartir con links
- 👥 Permisos básicos para familia/equipos
- 🔔 Notificaciones de actividad
- 🔒 Seguridad básica de documentos compartidos

---

## 🎯 EPIC 11: Documentación y Ayuda para Usuarios (Q4 2026)

**Prioridad:** 🟢 MEDIA
**Duración:** 2 semanas
**Dependencias:** EPIC 9 (UX)
**Objetivo:** Guías completas y ayuda contextual para usuarios

### Tareas (7 total)

- [ ] **TSK-2739:** Guía de inicio rápido para usuarios

  - Subtareas: getting_started, video_tutorials, screenshots
  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2740:** Documentación de features en español

  - Estimación: 3 días
  - Prioridad: Alta

- [ ] **TSK-2741:** Sistema de ayuda contextual (tooltips)

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2742:** FAQs de usuarios comunes

  - Estimación: 1 día
  - Prioridad: Media

- [ ] **TSK-2743:** Videos tutoriales cortos

  - Estimación: 3 días
  - Prioridad: Media

- [ ] **TSK-2744:** Troubleshooting guide

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2745:** Templates de documentos comunes
  - Estimación: 1 día
  - Prioridad: Baja

### Entregables

- 📚 Documentación completa en español
- 🎥 Videos tutoriales
- 💡 Ayuda contextual en la app
- 📋 Templates útiles

---

## 🎯 EPIC 12: Estabilidad y Refinamiento (Q4 2026)

**Prioridad:** 🟢 MEDIA-BAJA
**Duración:** 2 semanas
**Dependencias:** Todos los anteriores
**Objetivo:** Pulir features existentes, corregir bugs, mejorar estabilidad

### Tareas (5 total)

- [ ] **TSK-2746:** Bug bash - corrección de bugs reportados

  - Estimación: 5 días
  - Prioridad: Alta

- [ ] **TSK-2747:** Optimización de memoria en mobile

  - Estimación: 2 días
  - Prioridad: Media

- [ ] **TSK-2748:** Mejora de mensajes de error (más claros)

  - Estimación: 1.5 días
  - Prioridad: Media

- [ ] **TSK-2749:** Tests de regresión completos

  - Estimación: 2 días
  - Prioridad: Alta

- [ ] **TSK-2750:** Preparación para v3.0 release
  - Subtareas: release_notes, migration_guide, announcements
  - Estimación: 2 días
  - Prioridad: Alta

### Entregables

- 🐛 Bugs críticos corregidos
- 📱 Mobile más estable
- ✅ Suite de tests completa
- 📦 Release v3.0 lista

---

## 📅 Calendario de Entregas por Trimestre

### Q1 2026 (Enero - Marzo): Consolidación

**Semanas 1-13**

| Mes         | Epic            | Hitos Principales                                    |
| ----------- | --------------- | ---------------------------------------------------- |
| **Enero**   | EPIC 1 + EPIC 2 | ✅ Suite de tests completa, 📄 API documentada       |
| **Febrero** | EPIC 3 + EPIC 4 | 🚀 Performance +50%, 🔐 Encriptación activa          |
| **Marzo**   | Consolidación   | 🎯 Code freeze, 🧪 Regression tests, 📦 Release v2.0 |

**Entregables Q1:**

- Cobertura de tests >90%
- API totalmente documentada (Swagger)
- Performance mejorado 50% adicional
- Encriptación en reposo implementada
- Release v2.0.0 estable

---

### Q2 2026 (Abril - Junio): Expansión

**Semanas 14-26**

| Mes       | Epic                      | Hitos Principales                       |
| --------- | ------------------------- | --------------------------------------- |
| **Abril** | EPIC 5 (parte 1)          | 📱 Mobile app beta (iOS + Android)      |
| **Mayo**  | EPIC 5 (parte 2) + EPIC 6 | 📱 Mobile release, ☁️ Cloud sync activo |
| **Junio** | EPIC 7                    | 📊 Dashboard analytics, Release v2.1    |

**Entregables Q2:**

- Apps móviles en F-Droid + APK directo (100% gratis)
- Sync con Dropbox, Google Drive, OneDrive
- Estadísticas personales básicas
- Release v2.1.0

---

### Q3 2026 (Julio - Septiembre): UX y Compartir

**Semanas 27-39**

| Mes            | Epic    | Hitos Principales                                        |
| -------------- | ------- | -------------------------------------------------------- |
| **Julio**      | EPIC 8  | 💬 Comentarios y anotaciones en tiempo real              |
| **Agosto**     | EPIC 9  | 🎨 UX renovada, accesibilidad mejorada                   |
| **Septiembre** | EPIC 10 | 🔗 Sistema de compartir y permisos simples, Release v2.2 |

**Entregables Q3:**

- Sistema de colaboración para equipos pequeños
- Interfaz mejorada y más intuitiva
- Compartir documentos con familia/amigos
- Release v2.2.0 (enfoque en usuarios)

---

### Q4 2026 (Octubre - Diciembre): Documentación y Refinamiento

**Semanas 40-52**

| Mes           | Epic             | Hitos Principales                                       |
| ------------- | ---------------- | ------------------------------------------------------- |
| **Octubre**   | EPIC 10 (finish) | 🔗 Completar sistema de compartir                       |
| **Noviembre** | EPIC 11          | 📚 Documentación de usuario completa, videos tutoriales |
| **Diciembre** | EPIC 12 + Cierre | 🐛 Bug fixes, estabilidad, Release v3.0.0               |

**Entregables Q4:**

- Documentación completa en español
- Videos tutoriales para usuarios
- App estable y pulida
- Release v3.0.0 (listo para usuarios finales)
- Retrospectiva 2026

---

## 💰 Estimación de Recursos (Proyecto Open Source)

### Recursos Humanos (Contribución Voluntaria)

**Modelo Open Source:** Desarrollo basado en comunidad y contribuciones voluntarias

| Rol                     | Tiempo Estimado    | Modalidad             |
| ----------------------- | ------------------ | --------------------- |
| Maintainer Principal    | 10-15 hrs/semana   | Voluntario/Part-time  |
| Contribuidores Backend  | 5-8 hrs/semana c/u | Comunidad open source |
| Contribuidores Frontend | 5-8 hrs/semana c/u | Comunidad open source |
| Mobile Contributors     | 3-5 hrs/semana c/u | Comunidad open source |
| Code Reviewers          | 2-3 hrs/semana c/u | Comunidad open source |

**Estrategia de comunidad:**

- Fomentar contribuciones via GitHub Issues "good first issue"
- Hackatones trimestrales para features grandes
- Reconocimiento público de contribuidores en README
- Documentación clara para nuevos contribuidores

### Infraestructura y Servicios (Gratis/Open Source)

| Servicio              | Solución Gratuita                         | Notas                                    |
| --------------------- | ----------------------------------------- | ---------------------------------------- |
| **Hosting**           | Vercel/Netlify/GitHub Pages               | Hosting frontend gratis                  |
| **Backend**           | Fly.io/Railway (free tier)                | O self-hosted en servidor propio         |
| **Base de datos**     | PostgreSQL/MariaDB                        | Self-hosted o Supabase free tier         |
| **AI/ML**             | Modelos open source locales               | Hugging Face models, TrOCR, Tesseract    |
| **OCR**               | Tesseract OCR                             | Open source, self-hosted                 |
| **Monitoring**        | Sentry (free tier)                        | 5k eventos/mes gratis                    |
| **CI/CD**             | GitHub Actions                            | 2,000 min/mes gratis para repos públicos |
| **Blockchain**        | ❌ ELIMINADO (no necesario para usuarios) | $0                                       |
| **Mobile Publishing** | Solo F-Droid (Android) o APK directo      | **$0** (sin App Store/Google Play)       |
| **Storage**           | Self-hosted                               | $0                                       |
| **CDN**               | Cloudflare                                | Plan gratuito ilimitado                  |

### Costo Total Real

💵 **$0 USD/año** ✅ (100% GRATUITO - Proyecto Open Source)

**Estrategia 100% gratis:**

- ✅ Publicar APK directamente (sin Google Play)
- ✅ F-Droid para distribución Android (gratis)
- ✅ NO App Store (evitar $99/año)
- ✅ Solo servicios gratuitos y open source
- ✅ Self-hosting cuando sea necesario
- **Costo total: $0**

---

## 📊 Métricas de Éxito (KPIs)

### Métricas Técnicas

- ✅ **Code Coverage:** >90% (actual: ~75%)
- ✅ **API Response Time (p95):** <200ms (actual: ~500ms)
- ✅ **Crash-Free Rate:** >99.5%
- ✅ **Security Score:** A+ (actual: A)
- ✅ **Lighthouse Score (Web):** >90 (actual: ~75)

### Métricas de Comunidad

- 📈 **Usuarios Activos Mensuales (MAU):** +200% (1,000 → 3,000)
- 📈 **Documentos Procesados:** +150% (100k → 250k/mes)
- 📈 **Mobile Adoption:** 30% de usuarios en mobile
- 👥 **Contribuidores Activos:** 20+ contributors en GitHub
- ⭐ **GitHub Stars:** 1,000+ estrellas (indicador de adopción)

### Métricas de Producto

- ⭐ **NPS (Net Promoter Score):** >50
- ⭐ **App Store Rating:** >4.5 ⭐
- ⭐ **Customer Satisfaction:** >85%
- 🐛 **Bug Resolution Time:** <48h (P0-P1)

---

## 🚨 Riesgos y Mitigación

### Riesgos Técnicos

| Riesgo                                   | Probabilidad | Impacto | Mitigación                                   |
| ---------------------------------------- | ------------ | ------- | -------------------------------------------- |
| Performance degradation con encriptación | Media        | Alto    | Benchmark continuo, optimización incremental |
| Complejidad de multi-tenancy             | Alta         | Alto    | POC temprano, arquitectura revisada          |
| Integración blockchain costosa           | Media        | Medio   | Usar L2 (Polygon), hash anchoring selectivo  |
| AR/VR no adoptado                        | Alta         | Bajo    | Feature experimental, validar con usuarios   |

### Riesgos de Negocio

| Riesgo                          | Probabilidad | Impacto | Mitigación                                   |
| ------------------------------- | ------------ | ------- | -------------------------------------------- |
| Falta de recursos               | Media        | Alto    | Priorización estricta, contratación temprana |
| Competidores avanzan más rápido | Media        | Medio   | Features diferenciadores (IA, blockchain)    |
| Regulaciones GDPR cambian       | Baja         | Alto    | Compliance continuo, consultoría legal       |
| Adopción mobile baja            | Media        | Medio   | Marketing, onboarding mejorado               |

---

## 🔄 Proceso de Revisión del Roadmap

### Revisiones Mensuales

- 📅 **Frecuencia:** Primer viernes de cada mes
- 🎯 **Participantes:** Director (@dawnsystem), equipo de desarrollo
- 📊 **Agenda:**
  1. Review de épicas completadas
  2. Blockers y desafíos
  3. Ajuste de prioridades
  4. Actualización de timeline si necesario

### Revisiones Trimestrales

- 📅 **Frecuencia:** Última semana de cada trimestre
- 🎯 **Participantes:** Stakeholders + equipo
- 📊 **Agenda:**
  1. Demo de features completados
  2. Retrospectiva del trimestre
  3. Planeación del siguiente trimestre
  4. Ajuste de presupuesto

### Criterios para Ajustar el Roadmap

1. **Cambio en prioridades de negocio** → Re-priorizar épicas
2. **Feedback crítico de usuarios** → Insertar tareas urgentes
3. **Issues técnicos mayores** → Añadir tiempo de buffer
4. **Oportunidades de mercado** → Adelantar features clave

---

## 📚 Apéndice: Referencias

### Documentos Relacionados

- `agents.md` - Directivas del proyecto
- `BITACORA_MAESTRA.md` - Log histórico
- `IMPROVEMENT_ROADMAP.md` - Roadmap técnico detallado
- `DOCUMENTATION_INDEX.md` - Hub de documentación

### Standards y Compliance

- ISO 15489: Records Management
- DOD 5015.2: Electronic Records Management
- GDPR: General Data Protection Regulation
- SOC 2: Service Organization Control

### Herramientas Recomendadas

- **Project Management:** GitHub Projects, Notion
- **CI/CD:** GitHub Actions, CircleCI
- **Monitoring:** Sentry, Datadog, Grafana
- **Testing:** pytest, Jest, Detox
- **Documentation:** Swagger/OpenAPI, MkDocs

---

## ✅ Checklist de Implementación

Antes de iniciar cada EPIC, verificar:

- [ ] Dependencias completadas
- [ ] Recursos asignados
- [ ] Tests preparados
- [ ] Documentación ready
- [ ] Stakeholders notificados

Durante cada EPIC:

- [ ] Daily standups
- [ ] Update BITACORA_MAESTRA.md
- [ ] Commit siguiendo Conventional Commits
- [ ] Code reviews obligatorios
- [ ] Tests passing en CI/CD

Al completar cada EPIC:

- [ ] Demo functional
- [ ] Documentación actualizada
- [ ] Tests con cobertura >90%
- [ ] Security scan passed
- [ ] Release notes publicadas
- [ ] BITACORA_MAESTRA.md actualizada

---

**Fin del Roadmap 2026**

_Este documento es un organismo vivo. Se actualizará mensualmente según el progreso y feedback._

---

**Aprobado por:**
Director del Proyecto: @dawnsystem
Fecha de Aprobación: Pendiente
Versión: 1.0
