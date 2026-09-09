import { Component, OnDestroy, inject, signal } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import {
  NgbDropdownModule,
  NgbModal,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil, tap } from 'rxjs'
import { Document } from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { TrashService } from 'src/app/services/trash.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-trash',
  templateUrl: './trash.component.html',
  styleUrl: './trash.component.scss',
  imports: [
    PageHeaderComponent,
    PreviewPopupComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbDropdownModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
  ],
})
export class TrashComponent
  extends LoadingComponentWithPermissions
  implements OnDestroy
{
  private trashService = inject(TrashService)
  private toastService = inject(ToastService)
  private modalService = inject(NgbModal)
  private settingsService = inject(SettingsService)
  private router = inject(Router)
  private readonly emptyTrashDelaySetting =
    this.settingsService.getSignal<number>(SETTINGS_KEYS.EMPTY_TRASH_DELAY)

  readonly documentsInTrash = signal<Document[]>([])
  readonly selectedDocuments = signal<Set<number>>(new Set())
  readonly allToggled = signal(false)
  readonly page = signal(1)
  readonly totalDocuments = signal<number>(undefined)

  constructor() {
    super()
    this.reload()
  }

  reload() {
    this.loading.set(true)
    this.trashService
      .getTrash(this.page())
      .pipe(
        tap((r) => {
          this.documentsInTrash.set(r.results)
          this.totalDocuments.set(r.count)
          this.selectedDocuments.set(new Set())
          this.loading.set(false)
        })
      )
      .subscribe(() => {
        this.show.set(true)
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
        modal.componentInstance.buttonsEnabled.set(false)
        this.trashService.emptyTrash([document.id]).subscribe({
          next: () => {
            this.toastService.showInfo(
              $localize`Document "${document.title}" deleted`
            )
            modal.close()
            this.reload()
          },
          error: (err) => {
            this.toastService.showError(
              $localize`Error deleting document "${document.title}"`,
              err
            )
            modal.close()
          },
        })
      })
  }

  emptyTrash(documents?: Set<number>) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = documents
      ? $localize`This operation will permanently delete the selected documents.`
      : $localize`This operation will permanently delete all documents in the trash.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.trashService
          .emptyTrash(documents ? Array.from(documents) : null)
          .subscribe({
            next: () => {
              this.toastService.showInfo($localize`Document(s) deleted`)
              this.allToggled.set(false)
              modal.close()
              this.reload()
            },
            error: (err) => {
              this.toastService.showError(
                $localize`Error deleting document(s)`,
                err
              )
              modal.close()
            },
          })
      })
  }

  restore(document: Document) {
    this.trashService.restoreDocuments([document.id]).subscribe({
      next: () => {
        this.toastService.show({
          content: $localize`Document "${document.title}" restored`,
          delay: 5000,
          actionName: $localize`Open document`,
          action: () => {
            this.router.navigate(['documents', document.id])
          },
        })
        this.reload()
      },
      error: (err) => {
        this.toastService.showError(
          $localize`Error restoring document "${document.title}"`,
          err
        )
      },
    })
  }

  restoreAll(documents: Set<number> = null) {
    this.trashService
      .restoreDocuments(documents ? Array.from(documents) : null)
      .subscribe({
        next: () => {
          this.toastService.showInfo($localize`Document(s) restored`)
          this.allToggled.set(false)
          this.reload()
        },
        error: (err) => {
          this.toastService.showError(
            $localize`Error restoring document(s)`,
            err
          )
        },
      })
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedDocuments.set(
        new Set(this.documentsInTrash().map((t) => t.id))
      )
    } else {
      this.clearSelection()
    }
  }

  toggleSelected(object: Document) {
    const selectedDocuments = new Set(this.selectedDocuments())
    selectedDocuments.has(object.id)
      ? selectedDocuments.delete(object.id)
      : selectedDocuments.add(object.id)
    this.selectedDocuments.set(selectedDocuments)
  }

  clearSelection() {
    this.allToggled.set(false)
    this.selectedDocuments.set(new Set())
  }

  getDaysRemaining(document: Document): number {
    const delay = this.emptyTrashDelaySetting()
    const diff = new Date().getTime() - new Date(document.deleted_at).getTime()
    const days = Math.ceil(diff / (1000 * 3600 * 24))
    return delay - days
  }
}
