"""
Moteur de connexion et traitement IMAP pour Paperless-ngx

Gestion des connexions sécurisées, extraction d'e-mails et pièces jointes,
avec support OAuth2 et reconnexion automatique.
"""

import imaplib
import email
import ssl
import json
import logging
import time
import re
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import tempfile
import mimetypes

# OAuth2 et authentification
import requests
from requests.auth import HTTPBasicAuth

# Traitement de texte et extraction
import html2text
from bs4 import BeautifulSoup

# Détection de langue et extraction d'entités
try:
    from langdetect import detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False

from django.conf import settings
from django.utils import timezone as django_timezone
from django.core.files.base import ContentFile
from django.db import transaction

from .models import IMAPAccount, EmailMessage, EmailAttachment, EmailEvent, SyncLog


logger = logging.getLogger(__name__)


class IMAPConnectionError(Exception):
    """Erreur de connexion IMAP"""
    pass


class IMAPAuthenticationError(Exception):
    """Erreur d'authentification IMAP"""
    pass


class OAuth2Handler:
    """Gestionnaire OAuth2 pour IMAP"""

    def __init__(self, account: IMAPAccount):
        self.account = account
        self.logger = logging.getLogger(f"{__name__}.OAuth2Handler")

    def refresh_access_token(self) -> bool:
        """Actualise le token d'accès OAuth2"""
        if not self.account.oauth2_refresh_token:
            self.logger.error("Pas de refresh token disponible")
            return False

        try:
            # Configuration par provider
            provider_config = self._get_provider_config()
            if not provider_config:
                return False

            # Requête de refresh
            data = {
                'client_id': self.account.oauth2_client_id,
                'client_secret': self.account.oauth2_client_secret,
                'refresh_token': self.account.oauth2_refresh_token,
                'grant_type': 'refresh_token'
            }

            response = requests.post(
                provider_config['token_url'],
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()

                # Mise à jour des tokens
                self.account.oauth2_access_token = token_data['access_token']

                # Calcul de l'expiration
                expires_in = token_data.get('expires_in', 3600)
                self.account.oauth2_token_expires = (
                    django_timezone.now() + timedelta(seconds=expires_in - 300)  # 5min de marge
                )

                # Nouveau refresh token si fourni
                if 'refresh_token' in token_data:
                    self.account.oauth2_refresh_token = token_data['refresh_token']

                self.account.save(update_fields=[
                    'oauth2_access_token',
                    'oauth2_token_expires',
                    'oauth2_refresh_token'
                ])

                self.logger.info("Token OAuth2 actualisé avec succès")
                return True
            else:
                self.logger.error(f"Erreur refresh token: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Erreur lors du refresh OAuth2: {e}")
            return False

    def _get_provider_config(self) -> Optional[Dict]:
        """Retourne la configuration du provider OAuth2"""
        server = self.account.server.lower()

        if 'gmail' in server or 'google' in server:
            return {
                'token_url': 'https://oauth2.googleapis.com/token',
                'scope': 'https://mail.google.com/'
            }
        elif 'outlook' in server or 'office365' in server or 'microsoft' in server:
            return {
                'token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
                'scope': 'https://outlook.office.com/IMAP.AccessAsUser.All'
            }
        else:
            self.logger.warning(f"Provider OAuth2 non reconnu pour {server}")
            return None

    def get_oauth2_string(self) -> str:
        """Génère la chaîne d'authentification OAuth2 pour IMAP"""
        if not self.account.oauth2_access_token:
            raise IMAPAuthenticationError("Pas de token d'accès OAuth2")

        # Format SASL XOAUTH2
        auth_string = f"user={self.account.username}\x01auth=Bearer {self.account.oauth2_access_token}\x01\x01"
        return auth_string


class IMAPProcessor:
    """Processeur principal pour les connexions et traitements IMAP"""

    def __init__(self, account: IMAPAccount):
        self.account = account
        self.connection = None
        self.oauth2_handler = OAuth2Handler(account) if account.auth_method == 'oauth2' else None
        self.logger = logging.getLogger(f"{__name__}.IMAPProcessor")

        # Configuration pour extraction de texte
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True

        # Modèles NLP (si disponibles)
        self.nlp_model = None
        if HAS_SPACY:
            try:
                self.nlp_model = spacy.load("fr_core_news_sm")
            except OSError:
                try:
                    self.nlp_model = spacy.load("en_core_web_sm")
                except OSError:
                    self.logger.warning("Aucun modèle spaCy disponible")

    def connect(self) -> bool:
        """Établit la connexion IMAP"""
        try:
            # Création de la connexion
            if self.account.use_ssl:
                self.connection = imaplib.IMAP4_SSL(
                    self.account.server,
                    self.account.port
                )
            else:
                self.connection = imaplib.IMAP4(
                    self.account.server,
                    self.account.port
                )

                if self.account.use_starttls:
                    self.connection.starttls()

            # Authentification
            if self.account.auth_method == 'oauth2':
                return self._authenticate_oauth2()
            else:
                return self._authenticate_basic()

        except Exception as e:
            self.logger.error(f"Erreur de connexion IMAP: {e}")
            raise IMAPConnectionError(f"Impossible de se connecter: {e}")

    def _authenticate_oauth2(self) -> bool:
        """Authentification OAuth2"""
        try:
            # Vérification/actualisation du token
            if not self.account.is_oauth2_token_valid():
                if not self.oauth2_handler.refresh_access_token():
                    raise IMAPAuthenticationError("Impossible d'actualiser le token OAuth2")

            # Authentification IMAP
            auth_string = self.oauth2_handler.get_oauth2_string()
            self.connection.authenticate('XOAUTH2', lambda x: auth_string)

            self.logger.info("Authentification OAuth2 réussie")
            return True

        except Exception as e:
            self.logger.error(f"Erreur authentification OAuth2: {e}")
            raise IMAPAuthenticationError(f"Échec OAuth2: {e}")

    def _authenticate_basic(self) -> bool:
        """Authentification basique"""
        try:
            password = self.account.get_password()
            if not password:
                raise IMAPAuthenticationError("Mot de passe manquant")

            self.connection.login(self.account.username, password)

            self.logger.info("Authentification basique réussie")
            return True

        except Exception as e:
            self.logger.error(f"Erreur authentification basique: {e}")
            raise IMAPAuthenticationError(f"Échec authentification: {e}")

    def disconnect(self):
        """Ferme la connexion IMAP"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except Exception as e:
                self.logger.warning(f"Erreur lors de la déconnexion: {e}")
            finally:
                self.connection = None

    def sync_emails(self) -> SyncLog:
        """Synchronise les e-mails depuis le serveur IMAP"""
        sync_log = SyncLog.objects.create(
            account=self.account,
            status=SyncLog.STATUS_RUNNING
        )

        try:
            if not self.connection:
                if not self.connect():
                    raise IMAPConnectionError("Impossible de se connecter")

            # Synchronisation de tous les dossiers configurés
            folders = self.account.folders_to_sync or ['INBOX']
            total_emails = 0
            total_attachments = 0
            total_events = 0
            errors = 0

            for folder in folders:
                try:
                    self.logger.info(f"Synchronisation du dossier: {folder}")
                    stats = self._sync_folder(folder)

                    total_emails += stats.get('emails', 0)
                    total_attachments += stats.get('attachments', 0)
                    total_events += stats.get('events', 0)
                    errors += stats.get('errors', 0)

                except Exception as e:
                    self.logger.error(f"Erreur sync dossier {folder}: {e}")
                    errors += 1

            # Mise à jour du log
            sync_log.status = SyncLog.STATUS_SUCCESS
            sync_log.emails_processed = total_emails
            sync_log.attachments_processed = total_attachments
            sync_log.events_extracted = total_events
            sync_log.errors_count = errors
            sync_log.end_time = django_timezone.now()

            # Mise à jour du compte
            self.account.last_sync = django_timezone.now()
            self.account.sync_errors = []

        except Exception as e:
            self.logger.error(f"Erreur de synchronisation: {e}")
            sync_log.status = SyncLog.STATUS_ERROR
            sync_log.error_message = str(e)
            sync_log.end_time = django_timezone.now()

            # Ajout de l'erreur au compte
            errors = self.account.sync_errors or []
            errors.append({
                'timestamp': django_timezone.now().isoformat(),
                'error': str(e)
            })
            self.account.sync_errors = errors[-10:]  # Garde les 10 dernières erreurs

        finally:
            sync_log.save()
            self.account.save(update_fields=['last_sync', 'sync_errors'])
            self.disconnect()

        return sync_log

    def _sync_folder(self, folder: str) -> Dict[str, int]:
        """Synchronise un dossier spécifique"""
        stats = {'emails': 0, 'attachments': 0, 'events': 0, 'errors': 0}

        try:
            # Sélection du dossier
            status, data = self.connection.select(folder)
            if status != 'OK':
                raise Exception(f"Impossible de sélectionner le dossier {folder}")

            # Recherche des nouveaux e-mails (UID > dernier traité)
            search_criteria = f"UID {self.account.last_uid + 1}:*"

            # Application des filtres
            if self.account.sender_whitelist:
                sender_filter = ' OR '.join([f'FROM "{sender}"' for sender in self.account.sender_whitelist])
                search_criteria += f" ({sender_filter})"

            status, data = self.connection.uid('search', None, search_criteria)
            if status != 'OK':
                raise Exception(f"Erreur de recherche: {data}")

            uids = data[0].decode().split() if data[0] else []
            self.logger.info(f"Trouvé {len(uids)} nouveaux e-mails dans {folder}")

            # Traitement de chaque e-mail
            for uid in uids:
                try:
                    if self._process_email(uid, folder):
                        stats['emails'] += 1

                        # Mise à jour du dernier UID traité
                        self.account.last_uid = int(uid)

                except Exception as e:
                    self.logger.error(f"Erreur traitement e-mail UID {uid}: {e}")
                    stats['errors'] += 1

        except Exception as e:
            self.logger.error(f"Erreur sync dossier {folder}: {e}")
            stats['errors'] += 1

        return stats

    def _process_email(self, uid: str, folder: str) -> bool:
        """Traite un e-mail spécifique"""
        try:
            # Récupération de l'e-mail
            status, data = self.connection.uid('fetch', uid, '(RFC822)')
            if status != 'OK' or not data[0]:
                return False

            # Parsing de l'e-mail
            raw_email = data[0][1]
            parsed_email = email.message_from_bytes(raw_email)

            # Extraction des métadonnées
            message_id = parsed_email.get('Message-ID', f'generated-{uid}-{int(time.time())}')

            # Vérification des doublons
            if EmailMessage.objects.filter(account=self.account, message_id=message_id).exists():
                self.logger.debug(f"E-mail déjà traité: {message_id}")
                return False

            # Application des filtres
            if not self._should_process_email(parsed_email):
                self.logger.debug(f"E-mail filtré: {message_id}")
                return False

            # Création de l'objet e-mail
            with transaction.atomic():
                email_obj = self._create_email_object(parsed_email, uid, folder)

                # Traitement des pièces jointes
                if self.account.auto_process_attachments:
                    self._process_attachments(parsed_email, email_obj)

                # Extraction d'événements
                if self.account.auto_extract_events:
                    self._extract_events(email_obj)

                # Catégorisation automatique
                if self.account.auto_categorize:
                    self._categorize_email(email_obj)

                email_obj.is_processed = True
                email_obj.save()

            self.logger.info(f"E-mail traité avec succès: {email_obj.subject}")
            return True

        except Exception as e:
            self.logger.error(f"Erreur traitement e-mail UID {uid}: {e}")
            return False

    def _should_process_email(self, parsed_email) -> bool:
        """Vérifie si l'e-mail doit être traité selon les filtres"""

        # Vérification liste noire
        sender = parsed_email.get('From', '')
        if self.account.sender_blacklist:
            for blocked in self.account.sender_blacklist:
                if blocked.lower() in sender.lower():
                    return False

        # Vérification mots-clés sujet
        subject = parsed_email.get('Subject', '')
        if self.account.subject_keywords:
            has_keyword = any(
                keyword.lower() in subject.lower()
                for keyword in self.account.subject_keywords
            )
            if not has_keyword:
                return False

        return True

    def _create_email_object(self, parsed_email, uid: str, folder: str) -> EmailMessage:
        """Crée l'objet EmailMessage depuis l'e-mail parsé"""

        # Extraction des métadonnées
        message_id = parsed_email.get('Message-ID', f'generated-{uid}-{int(time.time())}')
        subject = self._decode_header(parsed_email.get('Subject', 'Sans sujet'))
        sender = self._extract_email_address(parsed_email.get('From', ''))

        # Dates
        date_sent = self._parse_email_date(parsed_email.get('Date'))

        # Destinataires
        recipients = self._extract_recipients(parsed_email.get('To', ''))
        cc_recipients = self._extract_recipients(parsed_email.get('Cc', ''))
        bcc_recipients = self._extract_recipients(parsed_email.get('Bcc', ''))

        # Extraction du contenu
        body_text, body_html = self._extract_body(parsed_email)

        # Détection de la priorité
        priority = self._detect_priority(parsed_email)

        # Détection de la langue
        detected_language = self._detect_language(body_text)

        # Création de l'objet
        email_obj = EmailMessage.objects.create(
            account=self.account,
            message_id=message_id,
            uid=int(uid),
            folder=folder,
            subject=subject,
            sender=sender,
            recipients=recipients,
            cc_recipients=cc_recipients,
            bcc_recipients=bcc_recipients,
            date_sent=date_sent,
            body_text=body_text,
            body_html=body_html,
            priority=priority,
            detected_language=detected_language,
        )

        return email_obj

    def _extract_body(self, parsed_email) -> Tuple[str, str]:
        """Extrait le corps de l'e-mail (texte et HTML)"""
        body_text = ""
        body_html = ""

        if parsed_email.is_multipart():
            for part in parsed_email.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Ignore les pièces jointes
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body_text = part.get_payload(decode=True).decode(charset, errors='ignore')
                    except Exception:
                        body_text = str(part.get_payload())

                elif content_type == "text/html":
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body_html = part.get_payload(decode=True).decode(charset, errors='ignore')
                        # Conversion HTML vers texte si pas de texte brut
                        if not body_text:
                            body_text = self.html_converter.handle(body_html)
                    except Exception:
                        body_html = str(part.get_payload())
        else:
            # E-mail simple (non-multipart)
            content_type = parsed_email.get_content_type()
            charset = parsed_email.get_content_charset() or 'utf-8'

            try:
                content = parsed_email.get_payload(decode=True).decode(charset, errors='ignore')

                if content_type == "text/html":
                    body_html = content
                    body_text = self.html_converter.handle(content)
                else:
                    body_text = content
            except Exception:
                body_text = str(parsed_email.get_payload())

        return body_text.strip(), body_html.strip()

    def _process_attachments(self, parsed_email, email_obj: EmailMessage):
        """Traite les pièces jointes de l'e-mail"""

        if not parsed_email.is_multipart():
            return

        for part in parsed_email.walk():
            content_disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in content_disposition or part.get_filename():
                try:
                    self._process_single_attachment(part, email_obj)
                except Exception as e:
                    self.logger.error(f"Erreur traitement pièce jointe: {e}")

    def _process_single_attachment(self, part, email_obj: EmailMessage):
        """Traite une pièce jointe individuelle"""

        # Métadonnées
        filename = self._decode_header(part.get_filename() or "unnamed")
        content_type = part.get_content_type()
        size = len(part.get_payload(decode=True) or b"")

        # Vérifications
        if size > self.account.max_attachment_size * 1024 * 1024:
            self.logger.warning(f"Pièce jointe trop grosse ignorée: {filename} ({size} bytes)")
            return

        extension = Path(filename).suffix.lower()
        if extension not in self.account.attachment_extensions:
            self.logger.debug(f"Extension non supportée ignorée: {filename}")
            return

        # Extraction du contenu
        content = part.get_payload(decode=True)
        if not content:
            return

        # Création de l'objet pièce jointe
        attachment = EmailAttachment.objects.create(
            email=email_obj,
            filename=filename,
            content_type=content_type,
            size=size,
            is_supported_format=self._is_supported_format(content_type)
        )

        # Stockage selon la taille
        if size < 1024 * 1024:  # < 1MB : stockage en base
            attachment.content = content
        else:  # > 1MB : fichier temporaire
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
            temp_file.write(content)
            temp_file.close()
            attachment.temp_file_path = temp_file.name

        attachment.save()

        # Traitement automatique si format supporté
        if attachment.is_supported_format:
            self._process_attachment_content(attachment)

        self.logger.info(f"Pièce jointe traitée: {filename}")

    def _process_attachment_content(self, attachment: EmailAttachment):
        """Traite le contenu d'une pièce jointe"""
        try:
            # Création d'un document Paperless-ngx
            from documents.consumer import ConsumerError
            from documents.models import Document

            # Préparation du contenu
            if attachment.content:
                file_content = attachment.content
            elif attachment.temp_file_path and Path(attachment.temp_file_path).exists():
                with open(attachment.temp_file_path, 'rb') as f:
                    file_content = f.read()
            else:
                raise Exception("Contenu de pièce jointe non trouvé")

            # Création du document via le système Paperless
            document = Document.objects.create(
                title=f"Email: {attachment.filename}",
                mime_type=attachment.content_type,
                checksum="",  # Sera calculé par le consumer
                size=attachment.size,
                source_path="",  # Sera défini par le consumer
            )

            # Association
            attachment.document = document
            attachment.is_processed = True
            attachment.save()

            self.logger.info(f"Document créé pour {attachment.filename}: ID {document.id}")

        except Exception as e:
            attachment.processing_error = str(e)
            attachment.save()
            self.logger.error(f"Erreur traitement contenu {attachment.filename}: {e}")

    def _extract_events(self, email_obj: EmailMessage):
        """Extrait les événements du contenu de l'e-mail"""

        # Combinaison du texte et sujet pour l'analyse
        full_text = f"{email_obj.subject}\n\n{email_obj.body_text}"

        # Patterns de détection d'événements
        events = []

        # Détection de réunions/RDV
        meeting_patterns = [
            r"réunion|meeting|rendez-vous|rdv|conference|call",
            r"agenda|calendar|planning",
            r"invitation|invite"
        ]

        # Détection de dates
        date_patterns = [
            r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",  # DD/MM/YYYY
            r"(\d{1,2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})",
            r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+(\d{1,2}[\/\-\.]\d{1,2})"
        ]

        # Détection d'heures
        time_patterns = [
            r"(\d{1,2}[h:]\d{2})",  # 14h30 ou 14:30
            r"(\d{1,2}\s*h\s*\d{2})",  # 14 h 30
        ]

        # Recherche de mots-clés d'événements
        text_lower = full_text.lower()
        event_keywords = []

        for pattern in meeting_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            event_keywords.extend(matches)

        if event_keywords:
            # Extraction plus approfondie avec NLP si disponible
            extracted_events = self._extract_events_nlp(full_text)

            for event_data in extracted_events:
                EmailEvent.objects.create(
                    email=email_obj,
                    **event_data
                )

    def _extract_events_nlp(self, text: str) -> List[Dict]:
        """Extraction d'événements avec traitement NLP"""
        events = []

        if not self.nlp_model:
            # Extraction basique sans NLP
            return self._extract_events_basic(text)

        try:
            # Analyse NLP
            doc = self.nlp_model(text)

            # Recherche d'entités temporelles et de localisation
            dates = []
            locations = []

            for ent in doc.ents:
                if ent.label_ in ["DATE", "TIME"]:
                    dates.append(ent.text)
                elif ent.label_ in ["GPE", "LOC"]:  # Geo-political entity, Location
                    locations.append(ent.text)

            # Construction d'événements basiques
            if dates:
                event = {
                    'event_type': EmailEvent.EVENT_MEETING,
                    'title': f"Événement extrait de: {text[:50]}...",
                    'description': text[:500],
                    'source_text': text,
                    'confidence_score': 0.7,
                    'extracted_keywords': dates + locations,
                }

                if locations:
                    event['location'] = locations[0]

                events.append(event)

        except Exception as e:
            self.logger.warning(f"Erreur extraction NLP: {e}")
            return self._extract_events_basic(text)

        return events

    def _extract_events_basic(self, text: str) -> List[Dict]:
        """Extraction d'événements basique sans NLP"""
        events = []

        # Patterns simples
        if any(keyword in text.lower() for keyword in ['réunion', 'meeting', 'rdv']):
            event = {
                'event_type': EmailEvent.EVENT_MEETING,
                'title': f"Réunion - {text[:50]}...",
                'description': text[:500],
                'source_text': text,
                'confidence_score': 0.5,
                'extracted_keywords': ['réunion'],
            }
            events.append(event)

        return events

    def _categorize_email(self, email_obj: EmailMessage):
        """Catégorise automatiquement l'e-mail"""

        # Analyse du contenu
        full_text = f"{email_obj.subject} {email_obj.body_text}".lower()

        # Mots-clés par catégorie
        category_keywords = {
            EmailMessage.CATEGORY_PROFESSIONAL: [
                'meeting', 'réunion', 'project', 'projet', 'report', 'rapport',
                'deadline', 'échéance', 'budget', 'contract', 'contrat'
            ],
            EmailMessage.CATEGORY_PERSONAL: [
                'famille', 'family', 'ami', 'friend', 'vacances', 'vacation',
                'anniversaire', 'birthday', 'personnel', 'personal'
            ],
            EmailMessage.CATEGORY_PROMOTIONAL: [
                'promotion', 'offer', 'offre', 'sale', 'discount', 'remise',
                'newsletter', 'publicité', 'advertising'
            ],
            EmailMessage.CATEGORY_SOCIAL: [
                'facebook', 'twitter', 'linkedin', 'instagram', 'social',
                'notification', 'comment', 'like', 'follow'
            ],
        }

        # Score par catégorie
        scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in full_text)
            scores[category] = score / len(keywords)  # Score normalisé

        # Sélection de la meilleure catégorie
        if scores:
            best_category = max(scores, key=scores.get)
            confidence = scores[best_category]

            if confidence > 0.1:  # Seuil minimum
                email_obj.category = best_category
                email_obj.confidence_score = confidence
                email_obj.save(update_fields=['category', 'confidence_score'])

    # Méthodes utilitaires

    def _decode_header(self, header_value: str) -> str:
        """Décode un en-tête d'e-mail"""
        if not header_value:
            return ""

        try:
            decoded = email.header.decode_header(header_value)
            result = ""

            for text, encoding in decoded:
                if isinstance(text, bytes):
                    result += text.decode(encoding or 'utf-8', errors='ignore')
                else:
                    result += text

            return result.strip()
        except Exception:
            return str(header_value).strip()

    def _extract_email_address(self, header_value: str) -> str:
        """Extrait l'adresse e-mail d'un en-tête"""
        if not header_value:
            return ""

        # Regex simple pour extraire l'e-mail
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, header_value)

        return match.group(0) if match else header_value.strip()

    def _extract_recipients(self, header_value: str) -> List[str]:
        """Extrait la liste des destinataires"""
        if not header_value:
            return []

        # Séparation par virgule et extraction des e-mails
        recipients = []
        for recipient in header_value.split(','):
            email_addr = self._extract_email_address(recipient.strip())
            if email_addr:
                recipients.append(email_addr)

        return recipients

    def _parse_email_date(self, date_header: str) -> datetime:
        """Parse la date d'un e-mail"""
        if not date_header:
            return django_timezone.now()

        try:
            return parsedate_to_datetime(date_header)
        except Exception:
            return django_timezone.now()

    def _detect_priority(self, parsed_email) -> str:
        """Détecte la priorité d'un e-mail"""

        # Headers de priorité
        priority_headers = [
            parsed_email.get('X-Priority'),
            parsed_email.get('Priority'),
            parsed_email.get('Importance')
        ]

        for header in priority_headers:
            if header:
                header_lower = header.lower()
                if 'high' in header_lower or 'urgent' in header_lower or '1' in header:
                    return 'high'
                elif 'low' in header_lower or '5' in header:
                    return 'low'

        # Analyse du sujet
        subject = parsed_email.get('Subject', '').lower()
        if any(word in subject for word in ['urgent', 'asap', 'important']):
            return 'high'

        return 'normal'

    def _detect_language(self, text: str) -> str:
        """Détecte la langue du texte"""
        if not HAS_LANGDETECT or not text.strip():
            return ""

        try:
            return detect(text)
        except Exception:
            return ""

    def _is_supported_format(self, content_type: str) -> bool:
        """Vérifie si le format est supporté par Paperless"""
        supported_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'image/tiff',
            'text/plain',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]

        return content_type in supported_types
