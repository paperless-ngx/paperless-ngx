# Module OCR Hybride Paperless-ngx

## Vue d'ensemble

Le module `paperless_ocr` fournit un système OCR hybride avancé pour Paperless-ngx, combinant la rapidité de Tesseract avec la précision de DocTR pour une reconnaissance de texte optimale.

## Fonctionnalités

### ✨ Moteurs OCR Multiples
- **Tesseract** : OCR rapide pour traitement en temps réel
- **DocTR** : OCR haute précision pour traitement en arrière-plan
- **Hybride** : Fusion intelligente des résultats pour la meilleure qualité

### 🔧 Configuration Avancée
- Interface d'administration Django complète
- Configurations multiples avec activation/désactivation
- Paramètres fins pour chaque moteur OCR
- Préprocessing d'image configurable

### 📊 Monitoring et APIs
- APIs REST complètes pour contrôle et monitoring
- Statistiques détaillées de performance
- Comparaison des résultats entre moteurs
- Interface d'administration riche

### ⚡ Performance Optimisée
- Traitement asynchrone avec Celery
- File d'attente prioritaire
- Gestion intelligente de la mémoire
- Mise en cache des résultats

## Installation

### 1. Dépendances Système

```bash
# Sur Debian/Ubuntu
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng

# Optionnel : autres langues
sudo apt install -y tesseract-ocr-deu tesseract-ocr-spa tesseract-ocr-ita
```

### 2. Dépendances Python

```bash
# Installation des packages requis
uv add pytesseract opencv-python-headless

# Optionnel : pour DocTR haute précision
uv add python-doctr
```

### 3. Configuration Django

Le module est déjà configuré dans `INSTALLED_APPS` :

```python
INSTALLED_APPS = [
    # ...
    "paperless_ocr.apps.PaperlessOcrConfig",
    # ...
]
```

### 4. Migrations

```bash
uv run python manage.py migrate paperless_ocr
```

## Configuration

### Configuration par Défaut

```python
from paperless_ocr.config import get_default_ocr_config

config = get_default_ocr_config()
```

### Paramètres Tesseract
- `tesseract_lang` : Langues (ex: "fra+eng")
- `tesseract_psm` : Page Segmentation Mode (1-13)
- `tesseract_oem` : OCR Engine Mode (0-3)

### Paramètres DocTR
- `doctr_model` : Modèle de détection
- `doctr_recognition_model` : Modèle de reconnaissance
- `doctr_assume_straight_pages` : Pages droites
- `doctr_detect_orientation` : Détection d'orientation

### Paramètres Généraux
- `dpi` : DPI pour conversion PDF (défaut: 300)
- `max_image_size` : Taille max images en pixels
- `enhance_image` : Amélioration d'image automatique
- `denoise` : Débruitage des images

## Utilisation

### Via l'Interface d'Administration

1. Allez dans **Django Admin > Paperless OCR**
2. Créez une nouvelle **Configuration OCR**
3. Activez la configuration souhaitée
4. Les documents seront traités automatiquement

### Via l'API REST

#### Déclencher l'OCR manuel
```bash
POST /api/ocr/documents/{id}/process/
{
    "engine": "hybrid",
    "priority": "high"
}
```

#### Consulter les résultats
```bash
GET /api/ocr/results/?document={id}
```

#### Statistiques
```bash
GET /api/ocr/documents/{id}/statistics/
```

### Via les Tâches Celery

```python
from paperless_ocr.tasks import process_document_ocr

# Traitement asynchrone
task = process_document_ocr.delay(document_id, engine="hybrid")
```

## Architecture

### Modèles de Données

#### OCRConfiguration
Configuration des moteurs OCR avec paramètres fins

#### OCRResult
Résultats OCR avec métadonnées, confiance et performances

#### OCRQueue
File d'attente des tâches OCR avec priorités

### Moteurs OCR

#### TesseractEngine
- Traitement rapide
- Bon pour scan simples
- Configuration flexible PSM/OEM

#### DoctrEngine
- Traitement précis
- Modèles deep learning
- Meilleur sur documents complexes

#### HybridEngine
- Fusion intelligente
- Sélection automatique du meilleur résultat
- Optimisation confidence/rapidité

## Signaux Django

Le module s'intègre automatiquement avec Paperless-ngx :

- **Import automatique** : OCR déclenché à l'import de documents
- **Nettoyage** : Suppression des données OCR si document supprimé
- **Mise à jour** : Retraitement si document modifié

## Monitoring

### Interface d'Administration
- Vue d'ensemble des configurations
- Statistiques de performance
- Actions en lot (activation, suppression)
- Badges colorés de statut

### APIs de Monitoring
- `/api/ocr/queue/` : État de la file d'attente
- `/api/ocr/statistics/` : Statistiques globales
- `/api/ocr/health/` : Santé du système

## Performance

### Optimisations Intégrées
- **Préprocessing d'image** : Amélioration automatique de la qualité
- **Mise en cache** : Résultats stockés en base
- **Traitement en lot** : Multiple documents simultanés
- **Gestion mémoire** : Libération automatique des ressources

### Métriques
- Temps de traitement par page
- Score de confiance
- Taux de réussite par moteur
- Utilisation mémoire

## Développement

### Structure du Code
```
paperless_ocr/
├── __init__.py
├── apps.py              # Configuration Django
├── models.py            # Modèles de données
├── engines.py           # Moteurs OCR
├── tasks.py             # Tâches Celery
├── views.py             # APIs REST
├── serializers.py       # Sérialisation DRF
├── admin.py             # Interface d'admin
├── signals.py           # Signaux Django
├── urls.py              # URLs API
├── config.py            # Configuration par défaut
├── requirements.txt     # Dépendances
└── test_setup.py        # Tests de validation
```

### Tests

```bash
# Test de fonctionnement
cd src && DISPLAY= QT_QPA_PLATFORM=offscreen uv run python paperless_ocr/test_setup.py

# Tests Django
uv run python manage.py test paperless_ocr
```

## Dépannage

### Tesseract non trouvé
```python
# Dans settings.py
TESSERACT_CMD = '/usr/bin/tesseract'
```

### Erreur OpenCV libGL
```bash
# Utilisez ces variables d'environnement
export DISPLAY=
export QT_QPA_PLATFORM=offscreen
```

### Problème de permissions
```bash
# Vérifiez les permissions des fichiers
chmod 644 /path/to/documents/*
```

## Support

### Langues Supportées
- Français (fra)
- Anglais (eng)
- Allemand (deu)
- Espagnol (spa)
- Italien (ita)

### Formats Supportés
- PDF
- PNG, JPEG, TIFF
- Multi-pages

## Évolutions Futures

- [ ] Support OCR Cloud (Google Vision, AWS Textract)
- [ ] Interface utilisateur dédiée
- [ ] Export des résultats en différents formats
- [ ] Analyse de mise en page avancée
- [ ] Support de langues RTL (arabe, hébreu)

---

**Note** : Ce module nécessite Paperless-ngx >= 2.0 et Python >= 3.9
