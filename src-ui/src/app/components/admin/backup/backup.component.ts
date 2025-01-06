import { Component, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { delay, takeUntil, tap } from 'rxjs'
import { Document } from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { BackupService } from 'src/app/services/backup.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { Backup } from 'src/app/data/backup'
import { PaperlessTask } from '../../../data/paperless-task'

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


  constructor(
    private backupService: BackupService,
    private toastService: ToastService,
    private modalService: NgbModal,
    private settingsService: SettingsService,
    private router: Router,
  ) {
    super()
    this.reload()
  }

  reload() {
    this.loading = true
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

  // delete(document: Document) {
  //   let modal = this.modalService.open(ConfirmDialogComponent, {
  //     backdrop: 'static',
  //   })
  //   modal.componentInstance.title = $localize`Confirm delete`
  //   modal.componentInstance.messageBold = $localize`This operation will permanently delete this document.`
  //   modal.componentInstance.message = $localize`This operation cannot be undone.`
  //   modal.componentInstance.btnClass = 'btn-danger'
  //   modal.componentInstance.btnCaption = $localize`Delete`
  //   modal.componentInstance.confirmClicked
  //     .pipe(takeUntil(this.unsubscribeNotifier))
  //     .subscribe(() => {
  //       modal.componentInstance.buttonsEnabled = false
  //       this.trashService.emptyTrash([document.id]).subscribe({
  //         next: () => {
  //           this.toastService.showInfo($localize`Document deleted`)
  //           modal.close()
  //           this.reload()
  //         },
  //         error: (err) => {
  //           this.toastService.showError($localize`Error deleting document`, err)
  //           modal.close()
  //         },
  //       })
  //     })
  // }

  // emptyTrash(documents?: Set<number>) {
  //   let modal = this.modalService.open(ConfirmDialogComponent, {
  //     backdrop: 'static',
  //   })
  //   modal.componentInstance.title = $localize`Confirm delete`
  //   modal.componentInstance.messageBold = documents
  //     ? $localize`This operation will permanently delete the selected documents.`
  //     : $localize`This operation will permanently delete all documents in the trash.`
  //   modal.componentInstance.message = $localize`This operation cannot be undone.`
  //   modal.componentInstance.btnClass = 'btn-danger'
  //   modal.componentInstance.btnCaption = $localize`Delete`
  //   modal.componentInstance.confirmClicked
  //     .pipe(takeUntil(this.unsubscribeNotifier))
  //     .subscribe(() => {
  //       this.trashService
  //         .emptyTrash(documents ? Array.from(documents) : null)
  //         .subscribe({
  //           next: () => {
  //             this.toastService.showInfo($localize`Document(s) deleted`)
  //             this.allToggled = false
  //             modal.close()
  //             this.reload()
  //           },
  //           error: (err) => {
  //             this.toastService.showError(
  //               $localize`Error deleting document(s)`,
  //               err
  //             )
  //             modal.close()
  //           },
  //         })
  //     })
  // }

  restore(backup: Backup) {
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
        this.reload()
      },
      error: (err) => {
        this.toastService.showError($localize`Error restoring document`, err)
      },
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
            $localize`Error restoring document(s)`,
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

  // getDaysTimeAgo(backup: Backup): number {
  //   const delay = this.settingsService.get(SETTINGS_KEYS.EMPTY_TRASH_DELAY)
  //   const diff = new Date().getTime() - new Date(backup.created_at).getTime()
  //   const days = Math.ceil(diff / (1000 * 3600 * 24))
  //   return delay - days
  // }
}
