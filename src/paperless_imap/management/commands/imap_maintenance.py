"""
Commande de maintenance IMAP pour Paperless-ngx

Effectue diverses opérations de maintenance sur le système IMAP :
- Nettoyage des logs anciens
- Suppression des e-mails orphelins
- Vérification de l'intégrité des données
- Mise à jour des statistiques
- Réparation des erreurs courantes

Usage:
    python manage.py imap_maintenance
    python manage.py imap_maintenance --cleanup-logs
    python manage.py imap_maintenance --check-integrity
    python manage.py imap_maintenance --update-stats
    python manage.py imap_maintenance --fix-orphans
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q, F
from django.db import transaction

from paperless_imap.models import (
    IMAPAccount, EmailMessage, EmailAttachment,
    EmailEvent, SyncLog
)
from paperless_imap.tasks import update_account_statistics
from documents.models import Document


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Commande de maintenance du système IMAP"""

    help = 'Effectue la maintenance du système IMAP'

    def add_arguments(self, parser):
        """Définition des arguments de la commande"""
        parser.add_argument(
            '--cleanup-logs',
            action='store_true',
            help='Nettoie les logs de synchronisation anciens'
        )

        parser.add_argument(
            '--logs-retention-days',
            type=int,
            default=30,
            help='Nombre de jours de rétention des logs (défaut: 30)'
        )

        parser.add_argument(
            '--check-integrity',
            action='store_true',
            help='Vérifie l\'intégrité des données IMAP'
        )

        parser.add_argument(
            '--fix-orphans',
            action='store_true',
            help='Répare les données orphelines'
        )

        parser.add_argument(
            '--update-stats',
            action='store_true',
            help='Met à jour les statistiques des comptes'
        )

        parser.add_argument(
            '--vacuum-database',
            action='store_true',
            help='Optimise la base de données (SQLite uniquement)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mode simulation sans modifications'
        )

        parser.add_argument(
            '--all',
            action='store_true',
            help='Effectue toutes les opérations de maintenance'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé'
        )

    def handle(self, *args, **options):
        """Point d'entrée principal de la commande"""

        # Configuration du logging
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        self.stdout.write(
            self.style.SUCCESS('=== Maintenance IMAP Paperless-ngx ===')
        )

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('MODE SIMULATION - Aucune modification ne sera effectuée')
            )

        # Exécution des opérations
        if options['all']:
            self._run_all_maintenance(options)
        else:
            if options['cleanup_logs']:
                self._cleanup_old_logs(options)

            if options['check_integrity']:
                self._check_data_integrity(options)

            if options['fix_orphans']:
                self._fix_orphaned_data(options)

            if options['update_stats']:
                self._update_account_statistics(options)

            if options['vacuum_database']:
                self._vacuum_database(options)

        self.stdout.write(
            self.style.SUCCESS('=== Maintenance terminée ===')
        )

    def _run_all_maintenance(self, options):
        """Exécute toutes les opérations de maintenance"""
        self.stdout.write("Exécution de toutes les opérations de maintenance...")

        self._cleanup_old_logs(options)
        self._check_data_integrity(options)
        self._fix_orphaned_data(options)
        self._update_account_statistics(options)
        self._vacuum_database(options)

    def _cleanup_old_logs(self, options):
        """Nettoie les logs de synchronisation anciens"""
        self.stdout.write("\n--- Nettoyage des logs anciens ---")

        retention_days = options['logs_retention_days']
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        old_logs = SyncLog.objects.filter(start_time__lt=cutoff_date)
        count = old_logs.count()

        if count == 0:
            self.stdout.write("Aucun log ancien à supprimer")
            return

        self.stdout.write(f"Logs à supprimer : {count} (plus de {retention_days} jours)")

        if not options['dry_run']:
            with transaction.atomic():
                deleted_count = old_logs.delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f"✓ {deleted_count} logs supprimés")
            )
        else:
            self.stdout.write(f"[SIMULATION] {count} logs seraient supprimés")

    def _check_data_integrity(self, options):
        """Vérifie l'intégrité des données IMAP"""
        self.stdout.write("\n--- Vérification de l'intégrité des données ---")

        issues = []

        # 1. E-mails sans compte
        orphaned_emails = EmailMessage.objects.filter(account__isnull=True)
        if orphaned_emails.exists():
            count = orphaned_emails.count()
            issues.append(f"E-mails orphelins (sans compte) : {count}")

        # 2. Pièces jointes sans e-mail
        orphaned_attachments = EmailAttachment.objects.filter(email__isnull=True)
        if orphaned_attachments.exists():
            count = orphaned_attachments.count()
            issues.append(f"Pièces jointes orphelines : {count}")

        # 3. Événements sans e-mail
        orphaned_events = EmailEvent.objects.filter(email__isnull=True)
        if orphaned_events.exists():
            count = orphaned_events.count()
            issues.append(f"Événements orphelins : {count}")

        # 4. Logs sans compte
        orphaned_logs = SyncLog.objects.filter(account__isnull=True)
        if orphaned_logs.exists():
            count = orphaned_logs.count()
            issues.append(f"Logs orphelins : {count}")

        # 5. Pièces jointes marquées comme traitées mais sans document
        processed_without_doc = EmailAttachment.objects.filter(
            is_processed=True,
            document__isnull=True
        )
        if processed_without_doc.exists():
            count = processed_without_doc.count()
            issues.append(f"PJ traitées sans document : {count}")

        # 6. Documents référencés qui n'existent plus
        attachments_with_invalid_docs = EmailAttachment.objects.filter(
            document__isnull=False
        ).exclude(
            document__in=Document.objects.all()
        )
        if attachments_with_invalid_docs.exists():
            count = attachments_with_invalid_docs.count()
            issues.append(f"PJ avec documents invalides : {count}")

        # 7. Comptes avec des erreurs de configuration
        invalid_accounts = IMAPAccount.objects.filter(
            Q(server='') | Q(username='') | Q(port__lt=1) | Q(port__gt=65535)
        )
        if invalid_accounts.exists():
            count = invalid_accounts.count()
            issues.append(f"Comptes mal configurés : {count}")

        # 8. E-mails avec des dates incohérentes
        emails_with_bad_dates = EmailMessage.objects.filter(
            date_sent__gt=timezone.now() + timedelta(days=1)
        )
        if emails_with_bad_dates.exists():
            count = emails_with_bad_dates.count()
            issues.append(f"E-mails avec dates futures : {count}")

        # Rapport
        if not issues:
            self.stdout.write(
                self.style.SUCCESS("✓ Aucun problème d'intégrité détecté")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ {len(issues)} problème(s) détecté(s) :")
            )
            for issue in issues:
                self.stdout.write(f"  - {issue}")

            self.stdout.write(
                "\nUtilisez --fix-orphans pour réparer automatiquement les données orphelines"
            )

    def _fix_orphaned_data(self, options):
        """Répare les données orphelines"""
        self.stdout.write("\n--- Réparation des données orphelines ---")

        fixed_count = 0

        # 1. Suppression des e-mails orphelins
        orphaned_emails = EmailMessage.objects.filter(account__isnull=True)
        if orphaned_emails.exists():
            count = orphaned_emails.count()
            self.stdout.write(f"Suppression de {count} e-mail(s) orphelin(s)")

            if not options['dry_run']:
                with transaction.atomic():
                    deleted = orphaned_emails.delete()[0]
                    fixed_count += deleted
                self.stdout.write(self.style.SUCCESS(f"✓ {deleted} e-mails supprimés"))
            else:
                self.stdout.write(f"[SIMULATION] {count} e-mails seraient supprimés")

        # 2. Suppression des pièces jointes orphelines
        orphaned_attachments = EmailAttachment.objects.filter(email__isnull=True)
        if orphaned_attachments.exists():
            count = orphaned_attachments.count()
            self.stdout.write(f"Suppression de {count} pièce(s) jointe(s) orpheline(s)")

            if not options['dry_run']:
                with transaction.atomic():
                    deleted = orphaned_attachments.delete()[0]
                    fixed_count += deleted
                self.stdout.write(self.style.SUCCESS(f"✓ {deleted} pièces jointes supprimées"))
            else:
                self.stdout.write(f"[SIMULATION] {count} pièces jointes seraient supprimées")

        # 3. Suppression des événements orphelins
        orphaned_events = EmailEvent.objects.filter(email__isnull=True)
        if orphaned_events.exists():
            count = orphaned_events.count()
            self.stdout.write(f"Suppression de {count} événement(s) orphelin(s)")

            if not options['dry_run']:
                with transaction.atomic():
                    deleted = orphaned_events.delete()[0]
                    fixed_count += deleted
                self.stdout.write(self.style.SUCCESS(f"✓ {deleted} événements supprimés"))
            else:
                self.stdout.write(f"[SIMULATION] {count} événements seraient supprimés")

        # 4. Suppression des logs orphelins
        orphaned_logs = SyncLog.objects.filter(account__isnull=True)
        if orphaned_logs.exists():
            count = orphaned_logs.count()
            self.stdout.write(f"Suppression de {count} log(s) orphelin(s)")

            if not options['dry_run']:
                with transaction.atomic():
                    deleted = orphaned_logs.delete()[0]
                    fixed_count += deleted
                self.stdout.write(self.style.SUCCESS(f"✓ {deleted} logs supprimés"))
            else:
                self.stdout.write(f"[SIMULATION] {count} logs seraient supprimés")

        # 5. Correction des pièces jointes traitées sans document
        processed_without_doc = EmailAttachment.objects.filter(
            is_processed=True,
            document__isnull=True
        )
        if processed_without_doc.exists():
            count = processed_without_doc.count()
            self.stdout.write(f"Correction de {count} PJ marquées comme traitées sans document")

            if not options['dry_run']:
                with transaction.atomic():
                    updated = processed_without_doc.update(is_processed=False)
                    fixed_count += updated
                self.stdout.write(self.style.SUCCESS(f"✓ {updated} PJ corrigées"))
            else:
                self.stdout.write(f"[SIMULATION] {count} PJ seraient corrigées")

        # 6. Correction des références de documents invalides
        attachments_with_invalid_docs = EmailAttachment.objects.filter(
            document__isnull=False
        ).exclude(
            document__in=Document.objects.all()
        )
        if attachments_with_invalid_docs.exists():
            count = attachments_with_invalid_docs.count()
            self.stdout.write(f"Correction de {count} PJ avec documents invalides")

            if not options['dry_run']:
                with transaction.atomic():
                    updated = attachments_with_invalid_docs.update(
                        document=None,
                        is_processed=False
                    )
                    fixed_count += updated
                self.stdout.write(self.style.SUCCESS(f"✓ {updated} PJ corrigées"))
            else:
                self.stdout.write(f"[SIMULATION] {count} PJ seraient corrigées")

        if fixed_count == 0 and not options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS("✓ Aucune donnée orpheline à réparer")
            )
        elif not options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {fixed_count} élément(s) réparé(s)")
            )

    def _update_account_statistics(self, options):
        """Met à jour les statistiques des comptes"""
        self.stdout.write("\n--- Mise à jour des statistiques ---")

        accounts = IMAPAccount.objects.all()
        updated_count = 0

        for account in accounts:
            self.stdout.write(f"Mise à jour des statistiques : {account.name}")

            if not options['dry_run']:
                try:
                    # Lancement de la tâche de mise à jour
                    update_account_statistics.delay(str(account.id))
                    updated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Tâche lancée pour {account.name}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Erreur pour {account.name} : {e}")
                    )
            else:
                self.stdout.write(f"[SIMULATION] Statistiques mises à jour pour {account.name}")
                updated_count += 1

        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {updated_count} compte(s) traité(s)")
            )
        else:
            self.stdout.write("Aucun compte à traiter")

    def _vacuum_database(self, options):
        """Optimise la base de données"""
        self.stdout.write("\n--- Optimisation de la base de données ---")

        from django.db import connection

        # Vérification du type de base de données
        if connection.vendor != 'sqlite':
            self.stdout.write(
                self.style.WARNING("Optimisation disponible uniquement pour SQLite")
            )
            return

        if options['dry_run']:
            self.stdout.write("[SIMULATION] Base de données optimisée")
            return

        try:
            with connection.cursor() as cursor:
                # VACUUM pour SQLite
                cursor.execute("VACUUM;")

                # Statistiques avant/après
                cursor.execute("PRAGMA page_count;")
                page_count = cursor.fetchone()[0]

                cursor.execute("PRAGMA page_size;")
                page_size = cursor.fetchone()[0]

                db_size = page_count * page_size

            self.stdout.write(
                self.style.SUCCESS(f"✓ Base de données optimisée ({db_size / 1024 / 1024:.2f} MB)")
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Erreur optimisation base de données : {e}")
            )
