"""
Module de gestion IMAP pour Paperless-ngx

Ce module fournit un système complet de gestion des e-mails IMAP avec :
- Connexions sécurisées (OAuth2, authentification classique)
- Extraction automatique des pièces jointes
- Indexation du contenu des e-mails
- Reconnaissance d'événements et métadonnées
- Interface d'administration complète
"""

default_app_config = 'paperless_imap.apps.PaperlessImapConfig'
