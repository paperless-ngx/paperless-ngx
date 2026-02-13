import { SlicePipe } from '@angular/common'
import {
  Component,
  EventEmitter,
  inject,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
} from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { merge, of, Subject } from 'rxjs'
import {
  filter,
  first,
  map,
  switchMap,
  take,
  takeUntil,
  tap,
} from 'rxjs/operators'
import { DocumentVersionInfo } from 'src/app/data/document'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ToastService } from 'src/app/services/toast.service'
import {
  UploadState,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { ConfirmButtonComponent } from '../../common/confirm-button/confirm-button.component'

@Component({
  selector: 'pngx-document-version-dropdown',
  templateUrl: './document-version-dropdown.component.html',
  imports: [
    FormsModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
    ConfirmButtonComponent,
    SlicePipe,
    CustomDatePipe,
  ],
})
export class DocumentVersionDropdownComponent implements OnChanges, OnDestroy {
  UploadState = UploadState

  @Input() documentId: number
  @Input() versions: DocumentVersionInfo[] = []
  @Input() selectedVersionId: number
  @Input() userCanEdit: boolean = false
  @Input() userIsOwner: boolean = false

  @Output() versionSelected = new EventEmitter<number>()
  @Output() versionsUpdated = new EventEmitter<DocumentVersionInfo[]>()

  newVersionLabel: string = ''
  versionUploadState: UploadState = UploadState.Idle
  versionUploadError: string | null = null

  private readonly documentsService = inject(DocumentService)
  private readonly toastService = inject(ToastService)
  private readonly websocketStatusService = inject(WebsocketStatusService)
  private readonly destroy$ = new Subject<void>()
  private readonly documentChange$ = new Subject<void>()

  ngOnChanges(changes: SimpleChanges): void {
    if (changes.documentId && !changes.documentId.firstChange) {
      this.documentChange$.next()
      this.clearVersionUploadStatus()
    }
  }

  ngOnDestroy(): void {
    this.documentChange$.next()
    this.documentChange$.complete()
    this.destroy$.next()
    this.destroy$.complete()
  }

  selectVersion(versionId: number): void {
    this.versionSelected.emit(versionId)
  }

  deleteVersion(versionId: number): void {
    const wasSelected = this.selectedVersionId === versionId
    this.documentsService
      .deleteVersion(this.documentId, versionId)
      .pipe(
        switchMap((result) =>
          this.documentsService
            .getVersions(this.documentId)
            .pipe(map((doc) => ({ doc, result })))
        ),
        first(),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: ({ doc, result }) => {
          if (doc?.versions) {
            this.versionsUpdated.emit(doc.versions)
          }

          if (wasSelected || this.selectedVersionId === versionId) {
            const fallbackId = result?.current_version_id ?? this.documentId
            this.versionSelected.emit(fallbackId)
          }
        },
        error: (error) => {
          this.toastService.showError($localize`Error deleting version`, error)
        },
      })
  }

  onVersionFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement
    if (!input?.files || input.files.length === 0) return
    const uploadDocumentId = this.documentId
    const file = input.files[0]
    input.value = ''
    const label = this.newVersionLabel?.trim()
    this.versionUploadState = UploadState.Uploading
    this.versionUploadError = null
    this.documentsService
      .uploadVersion(uploadDocumentId, file, label)
      .pipe(
        first(),
        tap(() => {
          this.toastService.showInfo(
            $localize`Uploading new version. Processing will happen in the background.`
          )
          this.newVersionLabel = ''
          this.versionUploadState = UploadState.Processing
        }),
        map((taskId) =>
          typeof taskId === 'string'
            ? taskId
            : (taskId as { task_id?: string })?.task_id
        ),
        switchMap((taskId) => {
          if (!taskId) {
            this.versionUploadState = UploadState.Failed
            this.versionUploadError = $localize`Missing task ID.`
            return of(null)
          }
          return merge(
            this.websocketStatusService.onDocumentConsumptionFinished().pipe(
              filter((status) => status.taskId === taskId),
              map(() => ({ state: 'success' as const }))
            ),
            this.websocketStatusService.onDocumentConsumptionFailed().pipe(
              filter((status) => status.taskId === taskId),
              map((status) => ({
                state: 'failed' as const,
                message: status.message,
              }))
            )
          ).pipe(takeUntil(merge(this.destroy$, this.documentChange$)), take(1))
        }),
        switchMap((result) => {
          if (result?.state !== 'success') {
            if (result?.state === 'failed') {
              this.versionUploadState = UploadState.Failed
              this.versionUploadError =
                result.message || $localize`Upload failed.`
            }
            return of(null)
          }
          return this.documentsService.getVersions(uploadDocumentId)
        }),
        takeUntil(this.destroy$),
        takeUntil(this.documentChange$)
      )
      .subscribe({
        next: (doc) => {
          if (uploadDocumentId !== this.documentId) return
          if (doc?.versions) {
            this.versionsUpdated.emit(doc.versions)
            this.versionSelected.emit(
              Math.max(...doc.versions.map((version) => version.id))
            )
            this.clearVersionUploadStatus()
          }
        },
        error: (error) => {
          if (uploadDocumentId !== this.documentId) return
          this.versionUploadState = UploadState.Failed
          this.versionUploadError = error?.message || $localize`Upload failed.`
          this.toastService.showError(
            $localize`Error uploading new version`,
            error
          )
        },
      })
  }

  clearVersionUploadStatus(): void {
    this.versionUploadState = UploadState.Idle
    this.versionUploadError = null
  }
}
