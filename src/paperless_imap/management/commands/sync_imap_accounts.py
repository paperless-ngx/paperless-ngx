"""
Commande de synchronisation IMAP pour Paperless-ngx

Synchronise tous les comptes IMAP actifs ou un compte spécifique.
Peut être utilisée dans des tâches cron ou des scripts automatisés.

Usage:
    python manage.py sync_imap_accounts
    python manage.py sync_imap_accounts --account-id UUID
    python manage.py sync_imap_accounts --force-full-sync
    python manage.py sync_imap_accounts --dry-run
"""

import logging
import sys
from datetime import datetime
from typing import List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q

from paperless_imap.models import IMAPAccount, SyncLog
from paperless_imap.tasks import sync_imap_account
from paperless_imap.imap_engine import IMAPProcessor, IMAPConnectionError, IMAPAuthenticationError


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Commande de synchronisation des comptes IMAP"""

    help = 'Synchronise les comptes IMAP actifs'

    def add_arguments(self, parser):
        """Définition des arguments de la commande"""
        parser.add_argument(
            '--account-id',
            type=str,
            help='ID du compte IMAP spécifique à synchroniser'
        )

        parser.add_argument(
            '--account-name',
            type=str,
            help='Nom du compte IMAP à synchroniser'
        )

        parser.add_argument(
            '--force-full-sync',
            action='store_true',
            help='Force une synchronisation complète (ignore la dernière sync)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mode simulation : teste les connexions sans synchroniser'
        )

        parser.add_argument(
            '--async',
            action='store_true',
            help='Lance la synchronisation en mode asynchrone (Celery)'
        )

        parser.add_argument(
            '--max-accounts',
            type=int,
            default=None,
            help='Nombre maximum de comptes à synchroniser'
        )

        parser.add_argument(
            '--timeout',
            type=int,
            default=300,
            help='Timeout en secondes pour chaque synchronisation (défaut: 300)'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé des opérations'
        )

    def handle(self, *args, **options):
        """Point d'entrée principal de la commande"""

        # Configuration du logging
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        self.stdout.write(
            self.style.SUCCESS('=== Synchronisation IMAP Paperless-ngx ===')
        )

        # Détermination des comptes à synchroniser
        accounts = self._get_accounts_to_sync(options)

        if not accounts:
            self.stdout.write(
                self.style.WARNING('Aucun compte IMAP à synchroniser')
            )
            return

        self.stdout.write(f"Comptes à synchroniser : {len(accounts)}")

        # Mode dry-run : test des connexions seulement
        if options['dry_run']:
            self._run_dry_run(accounts, options)
            return

        # Synchronisation effective
        if options['async']:
            self._run_async_sync(accounts, options)
        else:
            self._run_sync_sync(accounts, options)

    def _get_accounts_to_sync(self, options) -> List[IMAPAccount]:
        """Détermine quels comptes synchroniser"""

        # Compte spécifique par ID
        if options['account_id']:
            try:
                account = IMAPAccount.objects.get(id=options['account_id'])
                return [account]
            except IMAPAccount.DoesNotExist:
                raise CommandError(f"Compte avec ID {options['account_id']} introuvable")

        # Compte spécifique par nom
        if options['account_name']:
            try:
                account = IMAPAccount.objects.get(name=options['account_name'])
                return [account]
            except IMAPAccount.DoesNotExist:
                raise CommandError(f"Compte '{options['account_name']}' introuvable")
            except IMAPAccount.MultipleObjectsReturned:
                raise CommandError(f"Plusieurs comptes trouvés avec le nom '{options['account_name']}'")

        # Tous les comptes actifs
        queryset = IMAPAccount.objects.filter(is_active=True)

        # Limitation du nombre de comptes
        if options['max_accounts']:
            queryset = queryset[:options['max_accounts']]

        return list(queryset.order_by('last_sync', 'name'))

    def _run_dry_run(self, accounts: List[IMAPAccount], options):
        """Mode simulation : teste les connexions"""

        self.stdout.write(
            self.style.WARNING('=== MODE SIMULATION (DRY-RUN) ===')
        )

        success_count = 0
        error_count = 0

        for account in accounts:
            self.stdout.write(f"\nTest connexion : {account.name}")
            self.stdout.write(f"  Serveur : {account.server}:{account.port}")
            self.stdout.write(f"  Utilisateur : {account.username}")
            self.stdout.write(f"  SSL : {account.use_ssl}")
            self.stdout.write(f"  Auth : {account.auth_method}")

            try:
                processor = IMAPProcessor(account)
                if processor.connect():
                    # Test de base : liste des dossiers
                    folders = processor.list_folders()
                    processor.disconnect()

                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Connexion réussie ({len(folders)} dossiers)")
                    )
                    if options.get('verbose'):
                        for folder in folders[:5]:  # Affiche les 5 premiers dossiers
                            self.stdout.write(f"    - {folder}")
                        if len(folders) > 5:
                            self.stdout.write(f"    ... et {len(folders) - 5} autres")

                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR("  ✗ Échec de connexion")
                    )
                    error_count += 1

            except IMAPAuthenticationError as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Erreur d'authentification : {e}")
                )
                error_count += 1

            except IMAPConnectionError as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Erreur de connexion : {e}")
                )
                error_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Erreur inattendue : {e}")
                )
                error_count += 1

        # Résumé
        self.stdout.write(f"\n=== RÉSULTATS DU TEST ===")
        self.stdout.write(f"Connexions réussies : {success_count}")
        self.stdout.write(f"Connexions échouées : {error_count}")

        if error_count > 0:
            sys.exit(1)

    def _run_async_sync(self, accounts: List[IMAPAccount], options):
        """Synchronisation asynchrone via Celery"""

        self.stdout.write(
            self.style.WARNING('=== MODE ASYNCHRONE (CELERY) ===')
        )

        task_ids = []

        for account in accounts:
            try:
                task = sync_imap_account.delay(
                    str(account.id),
                    options['force_full_sync']
                )
                task_ids.append((account.name, task.id))

                self.stdout.write(
                    f"✓ Tâche lancée pour {account.name} : {task.id}"
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Erreur lancement tâche pour {account.name} : {e}")
                )

        self.stdout.write(f"\n{len(task_ids)} tâche(s) de synchronisation lancée(s)")

        if task_ids:
            self.stdout.write("\nTâches lancées :")
            for account_name, task_id in task_ids:
                self.stdout.write(f"  - {account_name} : {task_id}")

    def _run_sync_sync(self, accounts: List[IMAPAccount], options):
        """Synchronisation synchrone directe"""

        self.stdout.write(
            self.style.WARNING('=== MODE SYNCHRONE ===')
        )

        success_count = 0
        error_count = 0
        total_emails = 0
        total_attachments = 0

        for i, account in enumerate(accounts, 1):
            self.stdout.write(f"\n[{i}/{len(accounts)}] Synchronisation : {account.name}")

            try:
                # Création du log de synchronisation
                sync_log = SyncLog.objects.create(
                    account=account,
                    status=SyncLog.STATUS_RUNNING
                )

                start_time = timezone.now()
                processor = IMAPProcessor(account)

                # Connexion
                if not processor.connect():
                    raise IMAPConnectionError("Échec de connexion IMAP")

                self.stdout.write("  ✓ Connexion établie")

                # Synchronisation des dossiers
                folders_to_sync = account.get_folders_to_sync()
                self.stdout.write(f"  Dossiers à synchroniser : {len(folders_to_sync)}")

                emails_processed = 0
                attachments_processed = 0

                for folder in folders_to_sync:
                    self.stdout.write(f"    Synchronisation du dossier : {folder}")

                    folder_stats = processor.sync_folder(
                        folder,
                        force_full_sync=options['force_full_sync'],
                        max_emails=account.max_emails_per_sync
                    )

                    emails_processed += folder_stats.get('emails_processed', 0)
                    attachments_processed += folder_stats.get('attachments_processed', 0)

                    self.stdout.write(
                        f"      {folder_stats.get('emails_processed', 0)} e-mails, "
                        f"{folder_stats.get('attachments_processed', 0)} PJ"
                    )

                processor.disconnect()
                end_time = timezone.now()

                # Mise à jour du log
                sync_log.status = SyncLog.STATUS_SUCCESS
                sync_log.end_time = end_time
                sync_log.emails_processed = emails_processed
                sync_log.attachments_processed = attachments_processed
                sync_log.save()

                # Mise à jour du compte
                account.last_sync = end_time
                account.last_sync_status = 'success'
                account.save(update_fields=['last_sync', 'last_sync_status'])

                duration = end_time - start_time
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Synchronisation terminée en {duration.total_seconds():.1f}s"
                    )
                )
                self.stdout.write(
                    f"    E-mails traités : {emails_processed}"
                )
                self.stdout.write(
                    f"    Pièces jointes : {attachments_processed}"
                )

                success_count += 1
                total_emails += emails_processed
                total_attachments += attachments_processed

            except Exception as e:
                end_time = timezone.now()

                # Mise à jour du log d'erreur
                if 'sync_log' in locals():
                    sync_log.status = SyncLog.STATUS_ERROR
                    sync_log.end_time = end_time
                    sync_log.error_messages = str(e)[:1000]
                    sync_log.save()

                # Mise à jour du compte
                account.last_sync = end_time
                account.last_sync_status = 'error'
                account.save(update_fields=['last_sync', 'last_sync_status'])

                self.stdout.write(
                    self.style.ERROR(f"  ✗ Erreur synchronisation : {e}")
                )
                error_count += 1

                # Nettoyage de la connexion
                try:
                    if 'processor' in locals():
                        processor.disconnect()
                except:
                    pass

        # Résumé final
        self.stdout.write(f"\n=== RÉSUMÉ DE LA SYNCHRONISATION ===")
        self.stdout.write(f"Comptes synchronisés avec succès : {success_count}")
        self.stdout.write(f"Comptes en erreur : {error_count}")
        self.stdout.write(f"Total e-mails traités : {total_emails}")
        self.stdout.write(f"Total pièces jointes : {total_attachments}")

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{error_count} erreur(s) détectée(s). "
                    "Consultez les logs pour plus de détails."
                )
            )
            sys.exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ Toutes les synchronisations terminées avec succès")
            )
