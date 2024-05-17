import { Component, OnDestroy } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Document } from 'src/app/data/document'
import { ToastService } from 'src/app/services/toast.service'
import { TrashService } from 'src/app/services/trash.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { Subject, takeUntil } from 'rxjs'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'

@Component({
  selector: 'pngx-trash',
  templateUrl: './trash.component.html',
  styleUrl: './trash.component.scss',
})
export class TrashComponent implements OnDestroy {
  public documentsInTrash: Document[] = []
  public selectedDocuments: Set<number> = new Set()
  public allToggled: boolean = false
  public page: number = 1
  public totalDocuments: number
  public isLoading: boolean = false
  unsubscribeNotifier: Subject<void> = new Subject()

  constructor(
    private trashService: TrashService,
    private toastService: ToastService,
    private modalService: NgbModal,
    private settingsService: SettingsService
  ) {
    this.reload()
  }

  ngOnDestroy() {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  reload() {
    this.isLoading = true
    this.trashService.getTrash(this.page).subscribe((r) => {
      this.documentsInTrash = r.results
      this.totalDocuments = r.count
      this.isLoading = false
      this.selectedDocuments.clear()
    })
  }

  delete(document: Document) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this document.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        this.trashService.emptyTrash([document.id]).subscribe(() => {
          this.toastService.showInfo($localize`Document deleted`)
          this.reload()
        })
      })
  }

  emptyTrash(documents?: Set<number>) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete ${
      documents?.size ?? $localize`all`
    } documents in the trash.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.trashService
          .emptyTrash(documents ? Array.from(documents) : null)
          .subscribe(() => {
            this.toastService.showInfo($localize`Document(s) deleted`)
            this.allToggled = false
            this.reload()
          })
      })
  }

  restore(document: Document) {
    this.trashService.restoreDocuments([document.id]).subscribe(() => {
      this.toastService.showInfo($localize`Document restored`)
      this.reload()
    })
  }

  restoreAll(documents: Set<number> = null) {
    this.trashService
      .restoreDocuments(documents ? Array.from(documents) : null)
      .subscribe(() => {
        this.toastService.showInfo($localize`Document(s) restored`)
        this.allToggled = false
        this.reload()
      })
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedDocuments = new Set(this.documentsInTrash.map((t) => t.id))
    } else {
      this.clearSelection()
    }
  }

  toggleSelected(object: Document) {
    this.selectedDocuments.has(object.id)
      ? this.selectedDocuments.delete(object.id)
      : this.selectedDocuments.add(object.id)
  }

  clearSelection() {
    this.allToggled = false
    this.selectedDocuments.clear()
  }

  getDaysRemaining(document: Document): number {
    const delay = this.settingsService.get(SETTINGS_KEYS.EMPTY_TRASH_DELAY)
    const diff = new Date().getTime() - new Date(document.deleted_at).getTime()
    const days = Math.ceil(diff / (1000 * 3600 * 24))
    return delay - days
  }
}
