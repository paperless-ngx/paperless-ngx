# 📋 GitHub Projects - Configuración y Estructura

**Documento:** Guía completa para configurar GitHub Projects para IntelliDocs-ngx
**Fecha:** 2025-11-09
**Autoridad:** Siguiendo directivas de `agents.md`

---

## 🎯 Visión General

Este documento proporciona las instrucciones paso a paso para crear y configurar el GitHub Project que rastreará el progreso del **ROADMAP_2026.md** de IntelliDocs-ngx.

---

## 📊 Estructura del Project

### Información General del Project

- **Nombre:** IntelliDocs-ngx Roadmap 2026
- **Descripción:** Plan annual de desarrollo e implementación para IntelliDocs-ngx
- **Template:** Board (Kanban) + Roadmap views
- **Visibilidad:** Privado (solo equipo)

---

## 🚀 Paso 1: Crear el GitHub Project

### Opción A: Desde la Interfaz Web

1. Ir a: `https://github.com/orgs/dawnsystem/projects` (si es organización)
   O: `https://github.com/dawnsystem/IntelliDocs-ngx/projects` (si es repo)

2. Click en **"New project"**

3. Seleccionar template: **"Board"**

4. Configurar:

   - **Project name:** IntelliDocs-ngx Roadmap 2026
   - **Description:** Hoja de ruta completa para el año 2026. 12 Epics, 147 tareas, distribuidas en 4 trimestres.
   - **Visibility:** Private

5. Click **"Create project"**

### Opción B: Mediante GitHub CLI

```bash
# Instalar GitHub CLI si no está instalado
# brew install gh (macOS)
# apt install gh (Ubuntu/Debian)

# Autenticar
gh auth login

# Crear proyecto
gh project create \
  --owner dawnsystem \
  --title "IntelliDocs-ngx Roadmap 2026" \
  --body "Hoja de ruta completa para el año 2026. 12 Epics, 147 tareas, distribuidas en 4 trimestres."
```

---

## 📋 Paso 2: Configurar Columnas (Board View)

Crear las siguientes columnas en el Board:

### Columnas del Kanban

1. **📥 Backlog**

   - Status: Backlog
   - Descripción: Tareas no iniciadas, priorizadas para futuro

2. **📅 Planned (Q1-Q4)**

   - Status: Planned
   - Descripción: Tareas planificadas con trimestre asignado

3. **🔨 In Progress**

   - Status: In Progress
   - Descripción: Tareas en desarrollo activo

4. **👀 In Review**

   - Status: In Review
   - Descripción: Tareas completadas, esperando code review

5. **🧪 Testing**

   - Status: Testing
   - Descripción: Features en QA y testing

6. **✅ Done**

   - Status: Done
   - Descripción: Tareas completadas y mergeadas

7. **🚫 Blocked**
   - Status: Blocked
   - Descripción: Tareas bloqueadas por dependencias

---

## 🏷️ Paso 3: Configurar Labels (Etiquetas)

### Labels por Prioridad

```
🔴 priority: critical
🟠 priority: high
🟡 priority: medium
🟢 priority: low
```

### Labels por Epic

```
epic: 01-testing-qa
epic: 02-api-docs
epic: 03-performance
epic: 04-encryption
epic: 05-mobile
epic: 06-cloud-sync
epic: 07-analytics
epic: 08-collaboration
epic: 09-multi-tenancy
epic: 10-compliance
epic: 11-blockchain
epic: 12-ar-vr
```

### Labels por Trimestre

```
Q1-2026 (Enero-Marzo)
Q2-2026 (Abril-Junio)
Q3-2026 (Julio-Septiembre)
Q4-2026 (Octubre-Diciembre)
```

### Labels por Tipo

```
type: feature
type: enhancement
type: bug
type: documentation
type: test
type: infrastructure
```

### Labels por Área

```
area: backend
area: frontend
area: mobile
area: devops
area: ml-ai
area: ocr
area: security
```

### Commandos para crear labels (GitHub CLI)

```bash
# Prioridades
gh label create "priority: critical" --color "d73a4a" --description "Prioridad crítica"
gh label create "priority: high" --color "ff9900" --description "Prioridad alta"
gh label create "priority: medium" --color "fbca04" --description "Prioridad media"
gh label create "priority: low" --color "0e8a16" --description "Prioridad baja"

# Epics (12 totales)
gh label create "epic: 01-testing-qa" --color "0052cc" --description "EPIC 1: Testing y QA"
gh label create "epic: 02-api-docs" --color "0052cc" --description "EPIC 2: API Docs"
gh label create "epic: 03-performance" --color "0052cc" --description "EPIC 3: Performance"
gh label create "epic: 04-encryption" --color "0052cc" --description "EPIC 4: Encriptación"
gh label create "epic: 05-mobile" --color "0052cc" --description "EPIC 5: Mobile App"
gh label create "epic: 06-cloud-sync" --color "0052cc" --description "EPIC 6: Cloud Sync"
gh label create "epic: 07-analytics" --color "0052cc" --description "EPIC 7: Analytics"
gh label create "epic: 08-collaboration" --color "0052cc" --description "EPIC 8: Colaboración"
gh label create "epic: 09-multi-tenancy" --color "0052cc" --description "EPIC 9: Multi-tenancy"
gh label create "epic: 10-compliance" --color "0052cc" --description "EPIC 10: Compliance"
gh label create "epic: 11-blockchain" --color "0052cc" --description "EPIC 11: Blockchain"
gh label create "epic: 12-ar-vr" --color "0052cc" --description "EPIC 12: AR/VR"

# Trimestres
gh label create "Q1-2026" --color "fbca04" --description "Trimestre 1 (Enero-Marzo)"
gh label create "Q2-2026" --color "fbca04" --description "Trimestre 2 (Abril-Junio)"
gh label create "Q3-2026" --color "fbca04" --description "Trimestre 3 (Julio-Septiembre)"
gh label create "Q4-2026" --color "fbca04" --description "Trimestre 4 (Octubre-Diciembre)"

# Tipos
gh label create "type: feature" --color "a2eeef" --description "Nueva funcionalidad"
gh label create "type: enhancement" --color "a2eeef" --description "Mejora de funcionalidad existente"
gh label create "type: bug" --color "d73a4a" --description "Bug fix"
gh label create "type: documentation" --color "0075ca" --description "Documentación"
gh label create "type: test" --color "d4c5f9" --description "Testing"
gh label create "type: infrastructure" --color "fef2c0" --description "Infraestructura"

# Áreas
gh label create "area: backend" --color "c5def5" --description "Backend (Python/Django)"
gh label create "area: frontend" --color "c5def5" --description "Frontend (Angular/TypeScript)"
gh label create "area: mobile" --color "c5def5" --description "Mobile (React Native)"
gh label create "area: devops" --color "c5def5" --description "DevOps/CI-CD"
gh label create "area: ml-ai" --color "c5def5" --description "Machine Learning / AI"
gh label create "area: ocr" --color "c5def5" --description "OCR Avanzado"
gh label create "area: security" --color "c5def5" --description "Seguridad"
```

---

## 📊 Paso 4: Configurar Custom Fields

Agregar campos personalizados al project para tracking avanzado:

### 1. Epic (Single Select)

- **Nombre:** Epic
- **Tipo:** Single select
- **Opciones:**
  - EPIC 1: Testing y QA
  - EPIC 2: API Docs
  - EPIC 3: Performance
  - EPIC 4: Encriptación
  - EPIC 5: Mobile App
  - EPIC 6: Cloud Sync
  - EPIC 7: Analytics
  - EPIC 8: Colaboración
  - EPIC 9: Multi-tenancy
  - EPIC 10: Compliance
  - EPIC 11: Blockchain
  - EPIC 12: AR/VR

### 2. Trimestre (Single Select)

- **Nombre:** Trimestre
- **Tipo:** Single select
- **Opciones:**
  - Q1 2026 (Enero-Marzo)
  - Q2 2026 (Abril-Junio)
  - Q3 2026 (Julio-Septiembre)
  - Q4 2026 (Octubre-Diciembre)

### 3. Estimación (Number)

- **Nombre:** Estimación (días)
- **Tipo:** Number
- **Descripción:** Tiempo estimado en días de trabajo

### 4. Prioridad (Single Select)

- **Nombre:** Prioridad
- **Tipo:** Single select
- **Opciones:**
  - 🔴 Crítica
  - 🟠 Alta
  - 🟡 Media
  - 🟢 Baja

### 5. Progreso (Number)

- **Nombre:** Progreso (%)
- **Tipo:** Number
- **Descripción:** Porcentaje de completitud (0-100)

### 6. Fecha Inicio (Date)

- **Nombre:** Fecha Inicio
- **Tipo:** Date
- **Descripción:** Fecha de inicio de la tarea

### 7. Fecha Fin (Date)

- **Nombre:** Fecha Fin
- **Tipo:** Date
- **Descripción:** Fecha objetivo de finalización

### 8. Responsible (Person)

- **Nombre:** Responsible
- **Tipo:** Person
- **Descripción:** Persona asignada a la tarea

---

## 🗺️ Paso 5: Crear Vista de Roadmap

1. En el project, click en **"+ New view"**
2. Seleccionar **"Roadmap"**
3. Configurar:

   - **Name:** Roadmap 2026
   - **Date field (start):** Fecha Inicio
   - **Date field (end):** Fecha Fin
   - **Group by:** Epic
   - **Sort by:** Fecha Inicio (ascending)

4. Guardar vista

### Vista de Roadmap recomendada

- Mostrar markers por trimestre
- Color-code por prioridad
- Agrupar por Epic

---

## 📥 Paso 6: Importar Issues desde ROADMAP_2026.md

### Opción A: Manual (recomendado para iniciar)

Para cada tarea en ROADMAP_2026.md:

1. Crear un Issue en GitHub:

   ```
   Título: TSK-2601: Tests para classifier.py (clasificación BERT)

   Descripción:
   **Epic:** EPIC 1: Testing y QA
   **Prioridad:** Alta
   **Estimación:** 2 días
   **Trimestre:** Q1 2026

   ## Subtareas
   - [ ] test_train_model
   - [ ] test_predict
   - [ ] test_save_load
   - [ ] test_edge_cases

   ## Aceptación
   - Tests passing
   - Cobertura >90%
   - Documentado
   ```

2. Asignar labels:

   - `epic: 01-testing-qa`
   - `priority: high`
   - `Q1-2026`
   - `type: test`
   - `area: ml-ai`

3. Agregar al Project:
   - Click en "Projects" en el issue
   - Seleccionar "IntelliDocs-ngx Roadmap 2026"
   - Configurar custom fields

### Opción B: Script automatizado (para bulk import)

```python
#!/usr/bin/env python3
"""
Script para importar tareas del ROADMAP_2026.md a GitHub Issues
Require: pip install PyGithub
"""

from github import Github
import os

# Configuración
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_NAME = 'dawnsystem/IntelliDocs-ngx'
PROJECT_NUMBER = 1  # Ajustar al número del project

# Conectar a GitHub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# Definir tareas (ejemplo para EPIC 1)
tasks = [
    {
        'title': 'TSK-2601: Tests para classifier.py (clasificación BERT)',
        'body': '''**Epic:** EPIC 1: Testing y QA
**Prioridad:** Alta
**Estimación:** 2 días
**Trimestre:** Q1 2026

## Subtareas
- [ ] test_train_model
- [ ] test_predict
- [ ] test_save_load
- [ ] test_edge_cases

## Aceptación
- Tests passing
- Cobertura >90%
- Documentado''',
        'labels': ['epic: 01-testing-qa', 'priority: high', 'Q1-2026', 'type: test', 'area: ml-ai']
    },
    # ... más tareas
]

# Crear issues
for task in tasks:
    issue = repo.create_issue(
        title=task['title'],
        body=task['body'],
        labels=task['labels']
    )
    print(f"Created issue #{issue.number}: {issue.title}")
```

### Opción C: Usar GitHub CLI con loops

```bash
#!/bin/bash
# create_issues.sh

# EPIC 1 - Ejemplo
gh issue create \
  --title "TSK-2601: Tests para classifier.py (clasificación BERT)" \
  --body "**Epic:** EPIC 1: Testing y QA
**Prioridad:** Alta
**Estimación:** 2 días
**Trimestre:** Q1 2026

## Subtareas
- [ ] test_train_model
- [ ] test_predict
- [ ] test_save_load
- [ ] test_edge_cases" \
  --label "epic: 01-testing-qa" \
  --label "priority: high" \
  --label "Q1-2026" \
  --label "type: test" \
  --label "area: ml-ai"

# Repetir para cada tarea...
```

---

## 📊 Paso 7: Configurar Vistas Adicionales

### Vista 1: Por Prioridad

1. Crear nueva vista: **"Por Prioridad"**
2. Tipo: Board
3. Group by: Prioridad
4. Sort by: Fecha Inicio

### Vista 2: Por Trimestre

1. Crear nueva vista: **"Por Trimestre"**
2. Tipo: Board
3. Group by: Trimestre
4. Sort by: Epic

### Vista 3: Por Responsible

1. Crear nueva vista: **"Por Responsible"**
2. Tipo: Board
3. Group by: Responsible
4. Sort by: Prioridad

### Vista 4: Lista Completa

1. Crear nueva vista: **"Lista Completa"**
2. Tipo: Table
3. Mostrar todas las columnas
4. Sort by: ID (TSK-XXXX)

---

## 🔄 Paso 8: Configurar Automation

### Reglas de Automatización Recomendadas

1. **Auto-mover a "In Progress" cuando se asigna**

   - Trigger: Item assigned
   - Action: Set status to "In Progress"

2. **Auto-mover a "In Review" cuando se abre PR**

   - Trigger: Pull request opened
   - Action: Set status to "In Review"

3. **Auto-mover a "Done" cuando se cierra issue**

   - Trigger: Issue closed
   - Action: Set status to "Done"

4. **Auto-calcular progreso del Epic**
   - Usar GitHub Actions con script custom

### Configurar en Project Settings > Workflows

```yaml
# .github/workflows/project-automation.yml
name: Project Automation

on:
  issues:
    types: [opened, closed, assigned]
  pull_request:
    types: [opened, closed]

jobs:
  update-project:
    runs-on: ubuntu-latest
    steps:
      - name: Update project board
        uses: actions/add-to-project@v0.5.0
        with:
          project-url: https://github.com/orgs/dawnsystem/projects/1
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## 📈 Paso 9: Dashboard y Reporting

### Insights y Métricas

En el Project, habilitar Insights para ver:

1. **Burndown Chart**

   - Visualizar progreso vs tiempo
   - Ajustar por trimestre

2. **Velocity**

   - Tareas completadas por sprint/semana
   - Identificar bottlenecks

3. **Epic Progress**
   - % completitud de cada epic
   - Timeline vs plan original

### Export de Datos

```bash
# Exportar issues a CSV
gh project item-list 1 --owner dawnsystem --format csv > roadmap_export.csv
```

---

## 🔗 Paso 10: Integración con Repository

### Linkar Issues con PRs

En cada Pull Request, referenciar el issue:

```markdown
## Descripción

Implementa tests para el clasificador BERT.

## Issue Relacionado

Closes #123 (TSK-2601)

## Checklist

- [x] Tests añadidos
- [x] Tests passing
- [x] Documentación actualizada
```

### Plantilla de PR

Crear `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## 📋 Descripción

<!-- Describe los cambios -->

## 🎯 Issue Relacionado

Closes #<!-- número del issue -->

## 🧪 Testing

- [ ] Tests unitarios añadidos
- [ ] Tests de integración añadidos
- [ ] Tests passing en CI/CD

## 📚 Documentación

- [ ] README actualizado
- [ ] BITACORA_MAESTRA.md actualizada
- [ ] Comentarios en código

## ✅ Checklist

- [ ] Code review solicitado
- [ ] Linter passing
- [ ] No breaking changes
- [ ] Security scan passed
```

---

## 👥 Paso 11: Permisos y Colaboradores

### Asignar Roles

1. **Admin:** @dawnsystem (Director)

   - Puede editar project settings
   - Aprobar cambios al roadmap

2. **Write:** Developers

   - Pueden mover cards
   - Actualizar custom fields
   - Crear issues

3. **Read:** Stakeholders
   - Ver progreso
   - Comentar en issues

### Configurar en Project Settings > Manage access

---

## 📊 Ejemplo de Estructura Final

```
IntelliDocs-ngx Roadmap 2026
├── 📋 Board View
│   ├── 📥 Backlog (20 items)
│   ├── 📅 Planned (50 items)
│   ├── 🔨 In Progress (5 items)
│   ├── 👀 In Review (2 items)
│   ├── 🧪 Testing (1 item)
│   ├── ✅ Done (15 items)
│   └── 🚫 Blocked (0 items)
│
├── 🗺️ Roadmap View
│   ├── Q1 2026 (42 tareas)
│   ├── Q2 2026 (38 tareas)
│   ├── Q3 2026 (35 tareas)
│   └── Q4 2026 (32 tareas)
│
├── 📊 Por Prioridad
│   ├── 🔴 Crítica (15)
│   ├── 🟠 Alta (50)
│   ├── 🟡 Media (65)
│   └── 🟢 Baja (17)
│
└── 📈 Insights
    ├── Burndown Chart
    ├── Velocity
    └── Epic Progress
```

---

## 🎓 Best Practices

### 1. Actualización Regular

- ✅ Actualizar status de tasks **diariamente**
- ✅ Review del project board en **daily standup**
- ✅ Update de custom fields al cambiar estado

### 2. Granularidad de Tasks

- ✅ Tasks no más de 3-5 días
- ✅ Si una task es >5 días, dividirla en subtasks
- ✅ Usar subtasks en el issue description

### 3. Documentación

- ✅ Cada task debe tener acceptance criteria
- ✅ Link a documentación técnica cuando aplique
- ✅ Screenshots/videos de cambios UI

### 4. Code Reviews

- ✅ PR reviews obligatorios antes de merge
- ✅ Mínimo 1 aprobación requerida
- ✅ CI/CD debe pasar antes de merge

### 5. Comunicación

- ✅ Comentar en issues, no en Slack/email
- ✅ Tag (@mention) a personas relevantes
- ✅ Usar reactions para quick feedback

---

## 🔗 Links Útiles

- **GitHub Projects Docs:** https://docs.github.com/en/issues/planning-and-tracking-with-projects
- **GitHub CLI Docs:** https://cli.github.com/manual/
- **Project Templates:** https://github.com/orgs/community/discussions/categories/project-templates

---

## ✅ Checklist de Setup Completo

- [ ] Project creado
- [ ] Columnas configuradas (7 columnas)
- [ ] Labels creados (30+ labels)
- [ ] Custom fields agregados (8 campos)
- [ ] Vista Roadmap creada
- [ ] Vistas adicionales creadas (4 vistas)
- [ ] Issues importados (147 tareas)
- [ ] Automation configurada
- [ ] Permisos asignados
- [ ] Documentación compartida con equipo
- [ ] First sprint planning scheduled

---

**Próximos Pasos:**

1. Crear el GitHub Project siguiendo esta guía
2. Importar las primeras 20-30 tareas del EPIC 1
3. Asignar responsables
4. Programar primera reunión de sprint planning
5. Configurar integración con Notion (ver `NOTION_INTEGRATION_GUIDE.md`)

---

**Contacto:**
Director: @dawnsystem
Fecha: 2025-11-09
