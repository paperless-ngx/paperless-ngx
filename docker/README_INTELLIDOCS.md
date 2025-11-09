# 🐳 IntelliDocs Docker Files

Este directorio contiene todos los archivos necesarios para ejecutar IntelliDocs usando Docker.

## 📁 Estructura

```
docker/
├── compose/                          # Docker Compose configurations
│   ├── docker-compose.env           # Plantilla de variables de entorno (ACTUALIZADA)
│   ├── docker-compose.intellidocs.yml   # NUEVO: Compose optimizado para IntelliDocs
│   ├── docker-compose.sqlite.yml    # SQLite (más simple)
│   ├── docker-compose.postgres.yml  # PostgreSQL (producción)
│   ├── docker-compose.mariadb.yml   # MariaDB
│   └── docker-compose.*-tika.yml    # Con Apache Tika para OCR adicional
├── rootfs/                          # Sistema de archivos raíz del contenedor
├── test-intellidocs-features.sh    # NUEVO: Script de test para nuevas funciones
├── management_script.sh             # Scripts de gestión
└── README_INTELLIDOCS.md           # Este archivo

```

## 🚀 Inicio Rápido

### Opción 1: Usando el nuevo compose file optimizado (RECOMENDADO)

```bash
cd docker/compose

# Copiar y configurar variables de entorno
cp docker-compose.env docker-compose.env.local
nano docker-compose.env.local

# Crear directorios necesarios
mkdir -p data media export consume ml_cache

# Iniciar IntelliDocs con todas las nuevas funciones
docker compose -f docker-compose.intellidocs.yml up -d

# Ver logs
docker compose -f docker-compose.intellidocs.yml logs -f
```

### Opción 2: Usando compose files existentes

```bash
cd docker/compose

# Con SQLite (más simple)
docker compose -f docker-compose.sqlite.yml up -d

# Con PostgreSQL (recomendado para producción)
docker compose -f docker-compose.postgres.yml up -d

# Con MariaDB
docker compose -f docker-compose.mariadb.yml up -d
```

## ✅ Verificar Instalación

### Ejecutar script de test

```bash
cd docker
./test-intellidocs-features.sh
```

Este script verifica:
- ✓ Contenedores en ejecución
- ✓ Dependencias Python (torch, transformers, opencv, etc.)
- ✓ Módulos ML/OCR instalados
- ✓ Conexión a Redis
- ✓ Webserver respondiendo
- ✓ Variables de entorno configuradas
- ✓ Caché de modelos ML

## 🔧 Nuevas Funciones Disponibles

### Compose File Optimizado (`docker-compose.intellidocs.yml`)

Características especiales:
- ✨ **Redis optimizado** para caché con política LRU
- ✨ **Volumen ML cache** persistente para modelos
- ✨ **Health checks** mejorados
- ✨ **Resource limits** configurados para ML
- ✨ **Variables de entorno** pre-configuradas para nuevas funciones
- ✨ **Soporte GPU** (comentado, fácil de activar)

### Variables de Entorno Nuevas

En `docker-compose.env`:

```bash
# Habilitar funciones ML
PAPERLESS_ENABLE_ML_FEATURES=1

# Habilitar OCR avanzado  
PAPERLESS_ENABLE_ADVANCED_OCR=1

# Modelo ML a usar
PAPERLESS_ML_CLASSIFIER_MODEL=distilbert-base-uncased

# Usar GPU (requiere NVIDIA Docker)
PAPERLESS_USE_GPU=0

# Umbral para detección de tablas
PAPERLESS_TABLE_DETECTION_THRESHOLD=0.7

# Reconocimiento de manuscritos
PAPERLESS_ENABLE_HANDWRITING_OCR=1
```

## 📊 Comparación de Compose Files

| Característica | sqlite.yml | postgres.yml | intellidocs.yml |
|---------------|-----------|--------------|-----------------|
| Base de datos | SQLite | PostgreSQL | SQLite/Config |
| Redis básico | ✓ | ✓ | ✓ Optimizado |
| ML cache | ✗ | ✗ | ✓ Persistente |
| Health checks | Básico | Básico | ✓ Completo |
| Resource limits | ✗ | ✗ | ✓ Configurado |
| GPU ready | ✗ | ✗ | ✓ Preparado |
| Variables ML | ✗ | ✗ | ✓ Pre-config |

## 🏗️ Construir Imagen Local

Si necesitas modificar el código o construir tu propia imagen:

```bash
# Desde la raíz del proyecto
cd ..
docker build -t intellidocs-ngx:dev .

# Luego modificar docker-compose.intellidocs.yml para usar imagen local:
# image: intellidocs-ngx:dev
```

## 🔍 Comandos Útiles

### Gestión de contenedores

```bash
cd docker/compose

# Ver estado
docker compose -f docker-compose.intellidocs.yml ps

# Ver logs
docker compose -f docker-compose.intellidocs.yml logs -f webserver

# Reiniciar
docker compose -f docker-compose.intellidocs.yml restart

# Detener
docker compose -f docker-compose.intellidocs.yml down

# Detener y eliminar volúmenes (¡CUIDADO! Borra datos)
docker compose -f docker-compose.intellidocs.yml down -v
```

### Acceso al contenedor

```bash
# Shell en webserver
docker compose -f docker-compose.intellidocs.yml exec webserver bash

# Ejecutar comando de Django
docker compose -f docker-compose.intellidocs.yml exec webserver python manage.py <command>

# Crear superusuario
docker compose -f docker-compose.intellidocs.yml exec webserver python manage.py createsuperuser
```

### Debugging

```bash
# Ver recursos
docker stats

# Inspeccionar volúmenes
docker volume ls
docker volume inspect docker_ml_cache

# Ver tamaño de caché ML
docker compose -f docker-compose.intellidocs.yml exec webserver du -sh /usr/src/paperless/.cache/
```

## 📦 Volúmenes

### Volúmenes Originales

- `data`: Base de datos y configuración
- `media`: Documentos procesados
- `export`: Exportaciones
- `consume`: Documentos a procesar

### Volúmenes Nuevos (IntelliDocs)

- `ml_cache`: **NUEVO** - Caché de modelos ML (~500MB-1GB)
  - Persiste modelos descargados entre reinicios
  - Primera descarga puede tomar 5-10 minutos
  - Ubicación: `/usr/src/paperless/.cache/huggingface/`

## 🔧 Configuración Avanzada

### Activar Soporte GPU

1. Instalar NVIDIA Container Toolkit
2. En `docker-compose.intellidocs.yml`, descomentar:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```
3. Configurar: `PAPERLESS_USE_GPU=1`

### Ajustar Memoria

Para sistemas con menos RAM:

```yaml
deploy:
  resources:
    limits:
      memory: 4G  # Reducir de 8G
    reservations:
      memory: 2G  # Reducir de 4G
```

Y configurar workers:
```bash
PAPERLESS_TASK_WORKERS=1
PAPERLESS_THREADS_PER_WORKER=1
```

### Usar Base de Datos Externa

Modificar `docker-compose.intellidocs.yml` para usar PostgreSQL externo:

```yaml
environment:
  PAPERLESS_DBHOST: your-postgres-host
  PAPERLESS_DBPORT: 5432
  PAPERLESS_DBNAME: paperless
  PAPERLESS_DBUSER: paperless
  PAPERLESS_DBPASS: your-password
```

## 📚 Documentación Adicional

- **Guía completa**: `/DOCKER_SETUP_INTELLIDOCS.md`
- **Bitácora del proyecto**: `/BITACORA_MAESTRA.md`
- **Funciones implementadas**:
  - Fase 1: `/FASE1_RESUMEN.md` (Performance)
  - Fase 2: `/FASE2_RESUMEN.md` (Security)
  - Fase 3: `/FASE3_RESUMEN.md` (AI/ML)
  - Fase 4: `/FASE4_RESUMEN.md` (Advanced OCR)

## 🐛 Troubleshooting

### Problema: Modelos ML no se descargan

```bash
# Verificar conectividad
docker compose -f docker-compose.intellidocs.yml exec webserver ping -c 3 huggingface.co

# Descargar manualmente
docker compose -f docker-compose.intellidocs.yml exec webserver python -c "
from transformers import AutoTokenizer, AutoModel
model = 'distilbert-base-uncased'
AutoTokenizer.from_pretrained(model)
AutoModel.from_pretrained(model)
"
```

### Problema: Out of Memory

```bash
# Reducir workers en docker-compose.env.local
PAPERLESS_TASK_WORKERS=1
PAPERLESS_THREADS_PER_WORKER=1

# Aumentar memoria de Docker Desktop
# Settings → Resources → Memory → 8GB+
```

### Problema: Permisos de archivos

```bash
# Ajustar permisos
sudo chown -R 1000:1000 ./data ./media ./consume ./export ./ml_cache

# O configurar UID/GID
USERMAP_UID=$(id -u)
USERMAP_GID=$(id -g)
```

## 🎯 Próximos Pasos

1. ✅ Configurar variables de entorno
2. ✅ Ejecutar `docker-compose.intellidocs.yml`
3. ✅ Ejecutar test script
4. ✅ Crear superusuario
5. ✅ Subir documentos de prueba
6. ✅ Verificar funciones ML/OCR

---

**IntelliDocs** - Sistema de Gestión Documental con IA  
Versión: 1.0.0  
Última actualización: 2025-11-09
