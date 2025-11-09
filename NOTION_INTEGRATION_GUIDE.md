# 📘 Guía de Integración con Notion

**Documento:** Guía completa para integrar IntelliDocs-ngx Roadmap 2026 con Notion  
**Fecha:** 2025-11-09  
**Autoridad:** Siguiendo directivas de `agents.md`  
**Preferencia del Director:** Notion sobre Jira/Confluence

---

## 🎯 Visión General

Esta guía explica cómo integrar el GitHub Project de IntelliDocs-ngx con Notion para crear un workspace centralizado de gestión de proyectos, combinando lo mejor de ambas plataformas:

- **GitHub Projects:** Control técnico de issues, PRs, código
- **Notion:** Documentación, planificación estratégica, comunicación con stakeholders

---

## 🏗️ Arquitectura de Integración

```
┌─────────────────────────────────────────────────────────────┐
│                    NOTION WORKSPACE                          │
│  📊 Roadmap Dashboard | 📋 Tasks Database | 📖 Docs Wiki    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ Sync (2-way)
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               GITHUB PROJECT                                 │
│  🔨 Issues | 🔀 Pull Requests | 📈 Project Board            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Paso 1: Configurar Notion Workspace

### 1.1 Crear Workspace

1. Ir a https://notion.so
2. Crear cuenta o login
3. Crear nuevo workspace: **"IntelliDocs-ngx"**
4. Invitar a @dawnsystem como admin

### 1.2 Estructura del Workspace

Crear la siguiente jerarquía de páginas:

```
🏠 IntelliDocs-ngx Home
├── 📊 Roadmap 2026
│   ├── 🗺️ Timeline View
│   ├── 📋 Tasks Database
│   ├── 📈 Epic Dashboard
│   └── 📊 Progress Reports
├── 📚 Documentation
│   ├── 📘 Technical Docs
│   ├── 📗 User Guides
│   ├── 📕 API Reference
│   └── 📙 Architecture
├── 🎯 OKRs & Goals
│   ├── 2026 Objectives
│   └── KPIs Dashboard
├── 👥 Team
│   ├── Team Directory
│   └── Meeting Notes
└── 💬 Communications
    ├── Weekly Updates
    └── Announcements
```

---

## 📊 Paso 2: Crear Database de Tasks en Notion

### 2.1 Estructura de la Database

Crear una **Full-page database** llamada "Roadmap 2026 Tasks" con las siguientes propiedades:

| Property Name | Type | Options/Config |
|---------------|------|----------------|
| **Task ID** | Title | Formato: TSK-XXXX |
| **Status** | Select | Backlog, Planned, In Progress, In Review, Testing, Done, Blocked |
| **Epic** | Select | EPIC 1-12 (ver ROADMAP_2026.md) |
| **Prioridad** | Select | 🔴 Crítica, 🟠 Alta, 🟡 Media, 🟢 Baja |
| **Trimestre** | Select | Q1, Q2, Q3, Q4 2026 |
| **Estimación** | Number | Días de trabajo |
| **Progreso** | Number | Porcentaje (0-100) |
| **Fecha Inicio** | Date | - |
| **Fecha Fin** | Date | - |
| **Responsable** | Person | - |
| **GitHub Issue** | URL | Link al issue en GitHub |
| **GitHub PR** | URL | Link al PR cuando aplique |
| **Tags** | Multi-select | backend, frontend, mobile, ml-ai, ocr, security, devops |
| **Notas** | Text | Notas adicionales |
| **Subtareas** | Relation | Link a otra database de subtareas |

### 2.2 Template de Task

Crear un template para nuevas tasks:

```markdown
# {{Task ID}}: {{Título}}

## 📋 Descripción
[Descripción detallada de la tarea]

## 🎯 Epic
{{Epic}}

## 📅 Timeline
- **Inicio:** {{Fecha Inicio}}
- **Fin estimado:** {{Fecha Fin}}
- **Trimestre:** {{Trimestre}}

## 👤 Responsable
{{Responsable}}

## ✅ Subtareas
- [ ] Subtarea 1
- [ ] Subtarea 2
- [ ] Subtarea 3

## 📝 Criterios de Aceptación
- [ ] Criterio 1
- [ ] Criterio 2
- [ ] Criterio 3

## 🔗 Links
- GitHub Issue: {{GitHub Issue}}
- GitHub PR: {{GitHub PR}}
- Documentación relacionada: 

## 💬 Notas
[Notas adicionales, decisiones de diseño, etc.]
```

---

## 🔗 Paso 3: Integración GitHub ↔ Notion

### Opción A: Usando Notion API + GitHub Actions (Recomendado)

#### 3.1 Crear Integración en Notion

1. Ir a https://www.notion.so/my-integrations
2. Click en **"+ New integration"**
3. Configurar:
   - **Name:** IntelliDocs GitHub Sync
   - **Associated workspace:** IntelliDocs-ngx
   - **Type:** Internal integration
   - **Capabilities:**
     - ✅ Read content
     - ✅ Update content
     - ✅ Insert content

4. Guardar y copiar el **Internal Integration Token**

#### 3.2 Compartir Database con la Integración

1. Abrir la database "Roadmap 2026 Tasks" en Notion
2. Click en "..." (menú)
3. Seleccionar "Add connections"
4. Buscar y seleccionar "IntelliDocs GitHub Sync"

#### 3.3 Obtener Database ID

1. Abrir la database en el navegador
2. El URL será: `https://notion.so/{{workspace}}/{{database_id}}?v={{view_id}}`
3. Copiar el `database_id`

#### 3.4 Crear GitHub Action para Sync

Crear `.github/workflows/notion-sync.yml`:

```yaml
name: Sync GitHub Issues to Notion

on:
  issues:
    types: [opened, edited, closed, reopened, assigned]
  pull_request:
    types: [opened, closed, merged]
  schedule:
    # Sync cada hora
    - cron: '0 * * * *'
  workflow_dispatch:

jobs:
  sync-to-notion:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install notion-client PyGithub

      - name: Sync to Notion
        env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          NOTION_DATABASE_ID: ${{ secrets.NOTION_DATABASE_ID }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python .github/scripts/sync_github_to_notion.py
```

#### 3.5 Script de Sincronización

Crear `.github/scripts/sync_github_to_notion.py`:

```python
#!/usr/bin/env python3
"""
Sincroniza GitHub Issues con Notion Database
"""

import os
from notion_client import Client
from github import Github

# Configuración
NOTION_TOKEN = os.environ['NOTION_TOKEN']
NOTION_DATABASE_ID = os.environ['NOTION_DATABASE_ID']
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
REPO_NAME = 'dawnsystem/IntelliDocs-ngx'

# Clientes
notion = Client(auth=NOTION_TOKEN)
github = Github(GITHUB_TOKEN)
repo = github.get_repo(REPO_NAME)

def get_epic_from_labels(labels):
    """Extrae el Epic de los labels del issue"""
    for label in labels:
        if label.name.startswith('epic:'):
            return label.name.replace('epic: ', '').upper()
    return 'Sin Epic'

def get_priority_from_labels(labels):
    """Extrae la prioridad de los labels"""
    priority_map = {
        'priority: critical': '🔴 Crítica',
        'priority: high': '🟠 Alta',
        'priority: medium': '🟡 Media',
        'priority: low': '🟢 Baja'
    }
    for label in labels:
        if label.name in priority_map:
            return priority_map[label.name]
    return '🟡 Media'

def get_quarter_from_labels(labels):
    """Extrae el trimestre de los labels"""
    for label in labels:
        if label.name.startswith('Q'):
            return label.name
    return 'Backlog'

def get_status_from_issue(issue):
    """Determina el status basado en el estado del issue"""
    if issue.state == 'closed':
        return 'Done'
    elif issue.pull_request:
        return 'In Review'
    elif issue.assignee:
        return 'In Progress'
    else:
        return 'Planned'

def sync_issue_to_notion(issue):
    """Sincroniza un issue de GitHub a Notion"""
    
    # Buscar si ya existe en Notion
    results = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "GitHub Issue",
            "url": {"equals": issue.html_url}
        }
    )
    
    # Preparar propiedades
    properties = {
        "Task ID": {"title": [{"text": {"content": f"TSK-{issue.number}"}}]},
        "Status": {"select": {"name": get_status_from_issue(issue)}},
        "Epic": {"select": {"name": get_epic_from_labels(issue.labels)}},
        "Prioridad": {"select": {"name": get_priority_from_labels(issue.labels)}},
        "Trimestre": {"select": {"name": get_quarter_from_labels(issue.labels)}},
        "GitHub Issue": {"url": issue.html_url},
    }
    
    # Agregar responsable si existe
    if issue.assignee:
        properties["Responsable"] = {
            "people": [{"object": "user", "name": issue.assignee.login}]
        }
    
    # Agregar PR si existe
    if issue.pull_request:
        properties["GitHub PR"] = {"url": issue.pull_request.html_url}
    
    # Crear o actualizar en Notion
    if results['results']:
        # Actualizar existente
        page_id = results['results'][0]['id']
        notion.pages.update(page_id=page_id, properties=properties)
        print(f"✅ Updated: {issue.title}")
    else:
        # Crear nuevo
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties,
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "Descripción"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": issue.body or "Sin descripción"}}]
                    }
                }
            ]
        )
        print(f"✨ Created: {issue.title}")

def main():
    """Función principal"""
    print("🔄 Sincronizando GitHub Issues a Notion...")
    
    # Obtener todos los issues abiertos
    issues = repo.get_issues(state='all')
    
    count = 0
    for issue in issues:
        # Solo sincronizar issues con label de Epic
        if any(label.name.startswith('epic:') for label in issue.labels):
            sync_issue_to_notion(issue)
            count += 1
    
    print(f"\n✅ Sincronización completa: {count} issues procesados")

if __name__ == '__main__':
    main()
```

#### 3.6 Configurar Secrets en GitHub

1. Ir a: `https://github.com/dawnsystem/IntelliDocs-ngx/settings/secrets/actions`
2. Agregar secrets:
   - `NOTION_TOKEN`: Token de la integración de Notion
   - `NOTION_DATABASE_ID`: ID de la database de Notion

---

### Opción B: Usando Zapier (No-code, más fácil)

#### Configuración de Zap

1. Crear cuenta en https://zapier.com
2. Crear nuevo Zap: **"GitHub to Notion"**

**Trigger:**
- App: GitHub
- Event: New Issue
- Account: Conectar cuenta de GitHub
- Repository: dawnsystem/IntelliDocs-ngx

**Action:**
- App: Notion
- Event: Create Database Item
- Account: Conectar cuenta de Notion
- Database: Roadmap 2026 Tasks
- Mapear campos:
  - Task ID → Issue number
  - Status → "Planned"
  - Epic → Parse from labels
  - Prioridad → Parse from labels
  - GitHub Issue → Issue URL

3. Crear Zap inverso: **"Notion to GitHub"** (opcional)
   - Trigger: Updated Database Item in Notion
   - Action: Update Issue in GitHub

#### Limitaciones de Zapier
- ⚠️ Plan gratuito: 100 tasks/mes
- ⚠️ No sync bidireccional completo
- ⚠️ Latencia de ~5-15 minutos

**Costo:** $19.99/mes (plan Starter) para sync ilimitado

---

### Opción C: Usando Make (Integromat) - Alternativa a Zapier

Similar a Zapier pero con más control:
- Plan gratuito: 1,000 operations/mes
- Costo: $9/mes (plan Core)
- Mejor para workflows complejos

---

## 📊 Paso 4: Configurar Vistas en Notion

### Vista 1: Timeline (Gantt)

1. En la database, click en "+ New view"
2. Seleccionar **"Timeline"**
3. Configurar:
   - **Name:** Timeline View
   - **Date property (start):** Fecha Inicio
   - **Date property (end):** Fecha Fin
   - **Group by:** Epic
   - **Color by:** Prioridad

### Vista 2: Kanban Board

1. Crear nueva vista: **"Kanban Board"**
2. Tipo: Board
3. Configurar:
   - **Group by:** Status
   - **Sort by:** Prioridad
   - **Card preview:** Task ID, Responsable, Fecha Fin

### Vista 3: Por Epic

1. Crear vista: **"Por Epic"**
2. Tipo: Board
3. Group by: Epic
4. Sub-group by: Status

### Vista 4: Calendar

1. Crear vista: **"Calendario"**
2. Tipo: Calendar
3. Date property: Fecha Inicio
4. Color by: Epic

### Vista 5: Tabla Completa

1. Crear vista: **"Tabla Completa"**
2. Tipo: Table
3. Mostrar todas las propiedades
4. Sort by: Task ID

---

## 📈 Paso 5: Dashboard Ejecutivo en Notion

Crear una página "Epic Dashboard" con:

### 5.1 Progress Bars por Epic

Usar la función `Progress Bar` de Notion:

```
EPIC 1: Testing y QA
████████████░░░░░░░░ 60% (12/20 tasks)

EPIC 2: API Docs
████████████████████ 100% (8/8 tasks)

EPIC 3: Performance
███████░░░░░░░░░░░░░ 35% (7/20 tasks)
```

### 5.2 Linked Database Views

Insertar vistas filtradas de la database principal:

```markdown
## 🔥 Tareas Críticas
[Linked database: Filter by Prioridad = Crítica]

## 🚀 En Progreso Esta Semana
[Linked database: Filter by Status = In Progress]

## ⏰ Vencimientos Próximos (7 días)
[Linked database: Filter by Fecha Fin within next 7 days]
```

### 5.3 KPIs y Métricas

Usar fórmulas de Notion para calcular métricas:

```
📊 Total Tasks: {{count(all)}}
✅ Completadas: {{count(status = Done)}}
🔨 En Progreso: {{count(status = In Progress)}}
📅 Planificadas: {{count(status = Planned)}}

📈 Progreso General: {{count(Done) / count(all) * 100}}%
```

---

## 🗂️ Paso 6: Organizar Documentación en Notion

### 6.1 Migrar Documentos Markdown a Notion

**Opción A: Import manual**
1. Copiar contenido de archivos .md
2. Pegar en páginas de Notion
3. Notion convierte Markdown automáticamente

**Opción B: Usando markdown-to-notion**
```bash
npm install -g markdown-to-notion

markdown-to-notion \
  --token YOUR_NOTION_TOKEN \
  --page-id YOUR_PAGE_ID \
  --file ROADMAP_2026.md
```

### 6.2 Estructura de Documentación

```
📚 Documentation
├── 📘 Technical Docs
│   ├── ROADMAP_2026.md (importado)
│   ├── IMPROVEMENT_ROADMAP.md (importado)
│   ├── BITACORA_MAESTRA.md (sincronizado)
│   └── agents.md (referencia)
├── 📗 User Guides
│   ├── Getting Started
│   ├── Mobile App Guide
│   └── API Usage
├── 📕 API Reference
│   └── Swagger docs (embedded)
└── 📙 Architecture
    ├── System Architecture
    ├── Database Schema
    └── Deployment Diagram
```

---

## 🔔 Paso 7: Notificaciones y Comunicación

### 7.1 Configurar Notificaciones

En Notion Settings:
1. **My notifications:**
   - ✅ Updates to pages I'm subscribed to
   - ✅ @mentions
   - ✅ Comments and replies

2. **Email notifications:**
   - ✅ Daily digest (7:00 AM)
   - ⬜ Real-time (solo para @mentions críticos)

### 7.2 Integrar con Slack (opcional)

Si el equipo usa Slack:

1. Instalar Notion app en Slack
2. Conectar workspace de Notion
3. Configurar notificaciones:
   ```
   /notion subscribe #intellidocs-dev to "Roadmap 2026 Tasks"
   ```

4. Notificar en Slack cuando:
   - Nueva task creada
   - Task movida a "Done"
   - Comentario en task con prioridad crítica

---

## 📊 Paso 8: Reporting y Weekly Updates

### 8.1 Template de Weekly Update

Crear una database "Weekly Updates" con template:

```markdown
# Week {{week_number}} - {{date_range}}

## 🎯 Objetivos de la Semana
- [ ] Objetivo 1
- [ ] Objetivo 2
- [ ] Objetivo 3

## ✅ Completado
{{linked_view: tasks done this week}}

## 🔨 En Progreso
{{linked_view: tasks in progress}}

## 🚫 Bloqueadores
- Bloqueador 1: [descripción]
- Bloqueador 2: [descripción]

## 📈 Métricas
- **Velocity:** X tasks/semana
- **Burn rate:** Y% del sprint
- **Progreso general:** Z%

## 🎯 Próxima Semana
- Plan para semana siguiente
```

### 8.2 Monthly Reports

Template para reportes mensuales:

```markdown
# Monthly Report: {{month}} {{year}}

## 📊 Executive Summary
[Resumen de alto nivel para stakeholders]

## ✅ Epics Completados
{{linked_view: epics completed this month}}

## 🎯 Progress vs Plan
- **Planned:** X tasks
- **Completed:** Y tasks
- **Variance:** Z%

## 🌟 Highlights
- Logro importante 1
- Logro importante 2
- Logro importante 3

## ⚠️ Challenges
- Desafío 1 y cómo se resolvió
- Desafío 2 (en progreso)

## 🔮 Next Month Forecast
[Proyecciones para próximo mes]

## 📎 Attachments
- Screenshots
- Charts
- Links
```

---

## 🎨 Paso 9: Personalización y Branding

### 9.1 Cover Images

Agregar covers personalizados:
- Logo de IntelliDocs-ngx en página principal
- Imágenes temáticas por Epic
- Usar Unsplash integration de Notion

### 9.2 Icons

Asignar íconos a páginas:
- 🏠 Home
- 📊 Roadmap
- 📚 Docs
- 🎯 Goals
- 👥 Team
- 💬 Communications

### 9.3 Colores y Themes

Usar colores consistentes:
- 🔴 Crítico / Urgente
- 🟠 Alta prioridad
- 🟡 Media prioridad
- 🟢 Baja prioridad
- 🔵 Información / Docs
- 🟣 Innovación / R&D

---

## 🔒 Paso 10: Permisos y Seguridad

### 10.1 Configurar Permisos

1. **Workspace Settings** → **Members & Groups**
2. Crear grupos:
   - **Admins:** Full access
   - **Developers:** Can edit
   - **Stakeholders:** Can comment
   - **Guests:** Can view

3. Asignar permisos por página:
   - Roadmap: Developers (edit), Stakeholders (view)
   - Docs: Everyone (view), Developers (edit)
   - Team: Everyone (edit)

### 10.2 Compartir con Externos

Para compartir con usuarios sin cuenta:

1. Click en "Share" en la página
2. Seleccionar "Share to web"
3. Configurar:
   - ⬜ Allow search engines to index
   - ✅ Allow comments
   - ⬜ Allow editing

4. Generar link público (opcional)

---

## 📱 Paso 11: Mobile Access

### Notion Mobile Apps

1. Descargar Notion app:
   - iOS: App Store
   - Android: Google Play

2. Login con misma cuenta

3. Features disponibles en mobile:
   - Ver y editar tasks
   - Actualizar status
   - Comentar
   - Recibir notificaciones
   - Offline mode (sync al reconectar)

---

## 🔄 Paso 12: Workflow Completo

### Flujo de Trabajo Típico

1. **Nueva Feature Request:**
   ```
   User → GitHub Issue → Auto-sync → Notion Task
                                          ↓
                                     Priorizada en Planning
                                          ↓
                                     Asignada a Developer
   ```

2. **Durante Desarrollo:**
   ```
   Developer → Move to "In Progress" en Notion
                     ↓
                Updates sincronizados a GitHub
                     ↓
                Creates PR en GitHub
                     ↓
                Status en Notion: "In Review"
   ```

3. **Post-Merge:**
   ```
   PR merged → Issue closed → Status: "Done"
                                     ↓
                            Updated en Notion
                                     ↓
                        Reflected en Dashboard
   ```

---

## 💡 Tips y Best Practices

### 1. Mantener Notion como "Source of Truth" para Planning
- ✅ Planificación estratégica en Notion
- ✅ Tracking técnico en GitHub
- ✅ Sync automático entre ambos

### 2. Usar Templates
- ✅ Template para tasks
- ✅ Template para meeting notes
- ✅ Template para weekly updates

### 3. Embeds útiles
- Embed Figma designs
- Embed Google Sheets (para budgets)
- Embed Loom videos (demos)

### 4. Databases Relacionadas
- Link tasks a epics
- Link epics a OKRs
- Link docs a tasks

### 5. Mantener Limpio
- Archivar tasks viejas
- Review mensual de docs
- Actualizar templates según feedback

---

## 🆚 Comparación: Notion vs Jira/Confluence

| Feature | Notion | Jira + Confluence | Ganador |
|---------|--------|-------------------|---------|
| **Facilidad de uso** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Notion |
| **Flexibilidad** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Notion |
| **Features de PM** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Jira |
| **Documentación** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Notion |
| **Integraciones** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Jira |
| **Costo** | $8/user/mes | $7.75/user/mes | Empate |
| **Curva de aprendizaje** | Suave | Pronunciada | Notion |
| **Reporting** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Jira |

### Recomendación
✅ **Notion** es la mejor opción para IntelliDocs-ngx porque:
1. Equipo pequeño (1-5 personas)
2. Necesidad de flexibilidad
3. Documentación como prioridad
4. Integración sencilla con GitHub

---

## 📚 Recursos Adicionales

### Tutoriales Notion
- **Notion Academy:** https://www.notion.so/help/guides
- **YouTube:** Notion product management
- **Templates:** https://www.notion.so/templates

### Integraciones
- **Notion API:** https://developers.notion.com/
- **Zapier Notion:** https://zapier.com/apps/notion
- **Make Notion:** https://www.make.com/en/integrations/notion

### Comunidad
- **Reddit:** r/Notion
- **Discord:** Notion Community
- **Twitter:** @NotionHQ

---

## ✅ Checklist de Setup Completo

### Notion Setup
- [ ] Workspace creado
- [ ] Estructura de páginas configurada
- [ ] Database "Roadmap 2026 Tasks" creada
- [ ] Propiedades configuradas (12 campos)
- [ ] Templates creados (task, weekly update, monthly report)
- [ ] Vistas creadas (Timeline, Kanban, Calendar, Table)
- [ ] Dashboard ejecutivo configurado

### Integración
- [ ] Notion API integration creada
- [ ] GitHub Action configurada
- [ ] Secrets configurados en GitHub
- [ ] Primer sync exitoso
- [ ] Zapier/Make configurado (si aplica)

### Documentación
- [ ] Markdown docs migrados a Notion
- [ ] Wiki de documentación organizada
- [ ] API reference embedded

### Equipo
- [ ] Miembros invitados
- [ ] Permisos configurados
- [ ] Onboarding docs creados
- [ ] Primera reunión de planning agendada

---

## 🎯 Próximos Pasos

1. **Semana 1:** Setup básico de Notion + sync
2. **Semana 2:** Migrar docs y crear templates
3. **Semana 3:** Onboarding del equipo
4. **Semana 4:** Primera iteración con feedback

---

**Soporte:**  
Director: @dawnsystem  
Fecha: 2025-11-09  
Versión: 1.0

**Nota:** Este documento es parte de la iniciativa del ROADMAP_2026.md y sigue las directivas de agents.md
