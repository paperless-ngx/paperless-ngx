import { SlicePipe } from '@angular/common'
import {
  Component,
  EventEmitter,
  inject,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  signal,
  SimpleChanges,
} from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbDropdownModule, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { merge, of, Subject } from 'rxjs'
import {
  filter,
  finalize,
  first,
  map,
  switchMap,
  take,
  takeUntil,
  tap,
} from 'rxjs/operators'
import { DocumentVersionInfo } from 'src/app/data/document'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ToastService } from 'src/app/services/toast.service'
import {
  UploadState,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { ConfirmButtonComponent } from '../../common/confirm-button/confirm-button.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { AddExistingDocumentVersionDialogComponent } from './add-existing-document-version-dialog/add-existing-document-version-dialog.component'

@Component({
  selector: 'pngx-document-version-dropdown',
  templateUrl: './document-version-dropdown.component.html',
  styleUrls: ['./document-version-dropdown.component.scss'],
  imports: [
    FormsModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
    ConfirmButtonComponent,
    IfPermissionsDirective,
    SlicePipe,
    CustomDatePipe,
  ],
})
export class DocumentVersionDropdownComponent
  extends ComponentWithPermissions
  implements OnChanges, OnDestroy
{
  UploadState = UploadState

  @Input() documentId: number
  @Input() versions: DocumentVersionInfo[] = []
  @Input() selectedVersionId: number
  @Input() userCanEdit: boolean = false
  @Input() userIsOwner: boolean = false

  @Output() versionSelected = new EventEmitter<number>()
  @Output() versionsUpdated = new EventEmitter<DocumentVersionInfo[]>()

  newVersionLabel: string = ''
  readonly versionUploadState = signal(UploadState.Idle)
  readonly versionUploadError = signal<string | null>(null)
  readonly savingVersionLabelId = signal<number | null>(null)
  editingVersionId: number | null = null
  versionLabelDraft: string = ''

  private readonly documentsService = inject(DocumentService)
  private readonly toastService = inject(ToastService)
  private readonly websocketStatusService = inject(WebsocketStatusService)
  private readonly modalService = inject(NgbModal)
  private readonly destroy$ = new Subject<void>()
  private readonly documentChange$ = new Subject<void>()

  ngOnChanges(changes: SimpleChanges): void {
    if (changes.documentId && !changes.documentId.firstChange) {
      this.documentChange$.next()
      this.clearVersionUploadStatus()
      this.cancelEditingVersion()
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

  get canEditLabels(): boolean {
    return this.userIsOwner && this.userCanEdit
  }

  isEditingVersion(versionId: number): boolean {
    return this.editingVersionId === versionId
  }

  beginEditingVersion(version: DocumentVersionInfo, event?: Event): void {
    event?.preventDefault()
    event?.stopPropagation()
    if (!this.canEditLabels || this.savingVersionLabelId() !== null) return
    this.editingVersionId = version.id
    this.versionLabelDraft = version.version_label ?? ''
  }

  cancelEditingVersion(event?: Event): void {
    event?.preventDefault()
    event?.stopPropagation()
    this.editingVersionId = null
    this.versionLabelDraft = ''
  }

  submitEditedVersionLabel(version: DocumentVersionInfo, event?: Event): void {
    event?.preventDefault()
    event?.stopPropagation()
    if (this.savingVersionLabelId() !== null) return
    const nextLabel = this.versionLabelDraft?.trim() || null
    const currentLabel = version.version_label?.trim() || null
    if (nextLabel === currentLabel) {
      this.cancelEditingVersion()
      return
    }
    this.saveVersionLabel(version.id, nextLabel)
    this.cancelEditingVersion()
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

  saveVersionLabel(versionId: number, versionLabel: string | null): void {
    if (this.savingVersionLabelId() !== null) return
    this.savingVersionLabelId.set(versionId)
    this.documentsService
      .updateVersionLabel(this.documentId, versionId, versionLabel)
      .pipe(
        first(),
        finalize(() => {
          if (this.savingVersionLabelId() === versionId) {
            this.savingVersionLabelId.set(null)
          }
        }),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (updatedVersion) => {
          const updatedVersions = this.versions.map((version) =>
            version.id === versionId
              ? {
                  ...version,
                  version_label: updatedVersion.version_label,
                }
              : version
          )
          this.versionsUpdated.emit(updatedVersions)
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error updating version label`,
            error
          )
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
    this.versionUploadState.set(UploadState.Uploading)
    this.versionUploadError.set(null)
    this.documentsService
      .uploadVersion(uploadDocumentId, file, label)
      .pipe(
        first(),
        tap(() => {
          this.toastService.showInfo(
            $localize`Uploading new version. Processing will happen in the background.`
          )
          this.newVersionLabel = ''
          this.versionUploadState.set(UploadState.Processing)
        }),
        map((taskId) =>
          typeof taskId === 'string'
            ? taskId
            : (taskId as { task_id?: string })?.task_id
        ),
        switchMap((taskId) => {
          if (!taskId) {
            this.versionUploadState.set(UploadState.Failed)
            this.versionUploadError.set($localize`Missing task ID.`)
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
              this.versionUploadState.set(UploadState.Failed)
              this.versionUploadError.set(
                result.message || $localize`Upload failed.`
              )
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
          if (doc?.versions?.length) {
            this.versionsUpdated.emit(doc.versions)
            // The API returns versions newest first
            this.versionSelected.emit(doc.versions[0].id)
            this.clearVersionUploadStatus()
          }
        },
        error: (error) => {
          if (uploadDocumentId !== this.documentId) return
          this.versionUploadState.set(UploadState.Failed)
          this.versionUploadError.set(
            error?.message || $localize`Upload failed.`
          )
          this.toastService.showError(
            $localize`Error uploading new version`,
            error
          )
        },
      })
  }

  addExistingDocumentAsVersion(): void {
    const modal = this.modalService.open(
      AddExistingDocumentVersionDialogComponent,
      { backdrop: 'static' }
    )
    const dialog =
      modal.componentInstance as AddExistingDocumentVersionDialogComponent
    dialog.rootDocumentID = this.documentId
    dialog.confirmClicked
      .pipe(takeUntil(this.destroy$), takeUntil(this.documentChange$))
      .subscribe((existingDocumentID) => {
        dialog.buttonsEnabled.set(false)
        const versionLabel = this.newVersionLabel?.trim()
        this.documentsService
          .mergeDocumentsAsVersions(
            [this.documentId, existingDocumentID],
            this.documentId,
            versionLabel
          )
          .pipe(
            switchMap(() => this.documentsService.getVersions(this.documentId)),
            first(),
            finalize(() => dialog.buttonsEnabled.set(true)),
            takeUntil(this.destroy$),
            takeUntil(this.documentChange$)
          )
          .subscribe({
            next: (document) => {
              if (document?.versions?.length) {
                this.versionsUpdated.emit(document.versions)
                // The API returns versions newest first
                this.versionSelected.emit(document.versions[0].id)
              }
              this.newVersionLabel = ''
              modal.close()
              this.toastService.showInfo(
                $localize`Existing document added as a version.`
              )
            },
            error: (error) => {
              this.toastService.showError(
                $localize`Error adding existing document as a version`,
                error
              )
            },
          })
      })
  }

  clearVersionUploadStatus(): void {
    this.versionUploadState.set(UploadState.Idle)
    this.versionUploadError.set(null)
  }
}
