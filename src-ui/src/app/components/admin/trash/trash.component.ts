import { Component, OnDestroy } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Document } from 'src/app/data/document'
import { ToastService } from 'src/app/services/toast.service'
import { TrashService } from 'src/app/services/trash.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { Subject, takeUntil } from 'rxjs'

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
  public isLoading: boolean = false
  unsubscribeNotifier: Subject<void> = new Subject()

  constructor(
    private trashService: TrashService,
    private toastService: ToastService,
    private modalService: NgbModal
  ) {
    this.reload()
  }

  ngOnDestroy() {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  reload() {
    this.isLoading = true
    this.trashService.getTrash().subscribe((documentsInTrash) => {
      this.documentsInTrash = documentsInTrash
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

  emptyTrash(documents: Set<number> = null) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete ${
      documents?.size ?? $localize`all`
    } documents.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.trashService
          .emptyTrash(documents ? Array.from(documents) : [])
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

  restoreAll(objects: Set<number> = null) {
    this.trashService
      .restoreDocuments(objects ? Array.from(this.selectedDocuments) : [])
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
}
