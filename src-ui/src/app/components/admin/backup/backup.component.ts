import { Component, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { delay, takeUntil, tap } from 'rxjs'
import { Document } from 'src/app/data/document'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { BackupService } from 'src/app/services/backup.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { Backup } from 'src/app/data/backup'
import { BulkEditObjectOperation } from '../../../services/rest/abstract-name-filter-service'
import { SystemStatusService } from 'src/app/services/system-storage-status.service'
import { SystemStorageStatus } from 'src/app/data/system-storage-status'
import _default from 'chart.js/dist/plugins/plugin.tooltip'
import numbers = _default.defaults.animations.numbers

@Component({
  selector: 'pngx-backup',
  templateUrl: './backup.component.html',
  styleUrl: './backup.component.scss',
})
export class BackupComponent
  extends LoadingComponentWithPermissions
  implements OnDestroy {
  public backups: Backup[] = []
  public selectedBackups: Set<number> = new Set()
  public allToggled: boolean = false
  public page: number = 1
  public totalBackups: number
  public expandedBackup: number
  public systemStorageStatus: SystemStorageStatus
  public usedStorage: number = 0
  public totalStorage: number = 0
  public freeStorage: number = 0
  public anotherStorage: number = 0
  public documentStoragePercentage: number = 0
  public backupversionStoragePercentage: number = 0
  public availableStoragePercentage: number = 0
  public anotherPercentage: number = 0
  public documentStorage: number = 0
  public backupversionStorage: number = 0
  public availableStorage: number = 0



  constructor(
    private backupService: BackupService,
    private toastService: ToastService,
    private modalService: NgbModal,
    private settingsService: SettingsService,
    private systemStatusService: SystemStatusService,
    private router: Router,
  ) {
    super()
    this.reload()
  }

  reload() {
    this.loading = true
    this.systemStatusService.get().subscribe((status) => {
      this.systemStorageStatus = status
      this.loadDataStorageStatus(status)
    })

    this.backupService
      .getRecordBackup(this.page)
      .pipe(
        tap((r) => {
          this.backups = r.results
          this.totalBackups = r.count
          this.selectedBackups.clear()
          this.loading = false
        }),
        delay(100),
      )
      .subscribe(() => {
        this.show = true
      })
  }


  loadDataStorageStatus(systemStorageStatus: SystemStorageStatus) {
    this.usedStorage = systemStorageStatus.used
    this.totalStorage = systemStorageStatus.total
    this.anotherStorage = systemStorageStatus.another
    this.availableStorage = systemStorageStatus.available

    this.backupversionStorage = systemStorageStatus.backup
    this.documentStorage = systemStorageStatus.document
    this.freeStorage = this.totalStorage - this.usedStorage
    this.backupversionStoragePercentage = (this.backupversionStorage / this.totalStorage) * 100
    this.documentStoragePercentage = (this.documentStorage / this.totalStorage) * 100
    this.anotherPercentage = (this.anotherStorage / this.totalStorage) * 100
    this.availableStoragePercentage = 100 - this.backupversionStoragePercentage - this.documentStoragePercentage - this.anotherPercentage
  }

  restore(backup: Backup) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm restore`
    modal.componentInstance.messageBold = $localize`Please note that all changes after the restore will be lost. Are you sure you want to proceed?`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Restore`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        this.backupService.restore(backup.id).subscribe({
      next: () => {
        this.toastService.show({
          content: $localize`Document restored`,
          delay: 5000,
          actionName: $localize`Open document`,
          action: () => {
            this.router.navigate(['documents'])
          },
        })
        modal.close()
        this.reload()
      },
      error: (err) => {
        this.toastService.showError($localize`Error restoring document`, err)
        modal.close()
      },
        })
      })
  }

  delete(backup: Backup) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this backup version.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        this.backupService
          .bulk_edit_objects(
            Array.from([backup.id]),
            BulkEditObjectOperation.Delete,
            null,
            null,
          ).subscribe({
          next: () => {
            this.toastService.showInfo($localize`Backup version deleted`)
            modal.close()
            this.reload()
          },
          error: (err) => {
            this.toastService.showError($localize`Error deleting backup version`, err)
            modal.close()
          },
        })
      })
  }

  deleteBackups(backups?: Set<number>) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = backups
      ? $localize`This operation will permanently delete the selected backup versions.`
      : $localize`This operation will permanently delete all backup versions in the trash.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.backupService
          .bulk_edit_objects(
            Array.from(this.selectedBackups),
            BulkEditObjectOperation.Delete,
            null,
            null,
          )
          .subscribe({
            next: () => {
              this.toastService.showInfo($localize`Backup version(s) deleted`)
              this.allToggled = false
              modal.close()
              this.reload()
            },
            error: (error) => {
              this.toastService.showError(
                $localize`Error deleting backup version(s)`,
                error,
              )
              modal.close()
            },
          })
      })
  }

  backup() {
    this.backupService.backup()
      .subscribe({
        next: () => {
          this.toastService.showInfo($localize`Document(s) backed up`)
          this.allToggled = false
          this.reload()
        },
        error: (err) => {
          this.toastService.showError(
            $localize`Error backup document(s)`,
            err,
          )
        },
      })
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedBackups = new Set(this.backups.map((t) => t.id))
    } else {
      this.clearSelection()
    }
  }

  toggleSelected(object: Document) {
    this.selectedBackups.has(object.id)
      ? this.selectedBackups.delete(object.id)
      : this.selectedBackups.add(object.id)
  }

  clearSelection() {
    this.allToggled = false
    this.selectedBackups.clear()
  }

  expandBackup(backup: Backup) {
    this.expandedBackup = this.expandedBackup == backup.id ? undefined : backup.id
  }

}
