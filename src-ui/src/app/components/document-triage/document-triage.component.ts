import { Component, HostListener, OnInit, OnDestroy, inject } from '@angular/core'
import { Router } from '@angular/router'
import { FormControl, FormGroup, FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { PdfViewerModule } from 'ng2-pdf-viewer'
import { Subject, takeUntil, first, BehaviorSubject } from 'rxjs'
import { Document } from 'src/app/data/document'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { Tag } from 'src/app/data/tag'
import { DocumentService } from 'src/app/services/rest/document.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { TriageService, UndoAction } from 'src/app/services/triage.service'
import { ToastService } from 'src/app/services/toast.service'
import { HotKeyService } from 'src/app/services/hot-key.service'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { TagsComponent } from '../common/input/tags/tags.component'
import { SelectComponent } from '../common/input/select/select.component'
import { DateComponent } from '../common/input/date/date.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'

enum ZoomSetting {
  FitToWidth = 'page-width',
  FitToHeight = 'page-fit',
  One = 1.0,
}

@Component({
  selector: 'pngx-document-triage',
  templateUrl: './document-triage.component.html',
  styleUrls: ['./document-triage.component.scss'],
  imports: [
    PageHeaderComponent,
    TagsComponent,
    SelectComponent,
    DateComponent,
    FormsModule,
    ReactiveFormsModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
    PdfViewerModule,
    SafeUrlPipe,
  ],
})
export class DocumentTriageComponent implements OnInit, OnDestroy {
  private router = inject(Router)
  private documentService = inject(DocumentService)
  private correspondentService = inject(CorrespondentService)
  private documentTypeService = inject(DocumentTypeService)
  private tagService = inject(TagService)
  public triageService = inject(TriageService)
  private toastService = inject(ToastService)
  private hotKeyService = inject(HotKeyService)
  private settingsService = inject(SettingsService)

  private unsubscribeNotifier: Subject<any> = new Subject()

  currentDocument: Document | null = null
  previewUrl: string | null = null
  previewLoaded: boolean = false
  previewCurrentPage: number = 1
  previewZoomScale: ZoomSetting = ZoomSetting.FitToWidth
  useNativePdfViewer: boolean = false

  correspondents: Correspondent[] = []
  documentTypes: DocumentType[] = []
  tags: Tag[] = []

  isSaving: boolean = false

  documentForm: FormGroup = new FormGroup({
    correspondent: new FormControl(null),
    document_type: new FormControl(null),
    tags: new FormControl([]),
    created: new FormControl(null),
  })

  private shortcutHandlers: (() => void)[] = []

  ngOnInit(): void {
    // Check if triage is initialized
    const state = this.triageService.getState()
    if (!state || state.documents.length === 0) {
      this.toastService.showInfo($localize`No documents to triage`)
      this.router.navigate(['/documents'])
      return
    }

    // Load metadata options
    this.loadCorrespondents()
    this.loadDocumentTypes()
    this.loadTags()

    // Load the first document
    this.loadCurrentDocument()

    // Subscribe to triage state changes - only reload when index changes
    let lastIndex = -1
    this.triageService.triageState$
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((state) => {
        if (!state || state.documents.length === 0) {
          this.exitTriage()
        } else if (state.currentIndex !== lastIndex) {
          // Only reload if the current index changed
          lastIndex = state.currentIndex
          this.loadCurrentDocument()
        }
      })

    // Setup keyboard shortcuts
    this.setupKeyboardShortcuts()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
    // Clean up keyboard shortcuts
    this.shortcutHandlers.forEach((handler) => handler())
  }

  @HostListener('document:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent): void {
    // Don't trigger shortcuts if user is typing in an input/textarea
    const target = event.target as HTMLElement
    const isInputField = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
    
    // For T and C keys, we want them to work when NOT in an input
    if (event.key.toLowerCase() === 't' && !isInputField) {
      event.preventDefault()
      this.focusTagInput()
      return
    }
    
    if (event.key.toLowerCase() === 'c' && !isInputField) {
      event.preventDefault()
      this.focusCorrespondentInput()
      return
    }

    // For these keys, they should work regardless of input focus (but not with modifiers)
    if (event.key.toLowerCase() === 'n' && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      this.nextDocument()
      return
    }
    
    if (event.key.toLowerCase() === 'p' && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      this.previousDocument()
      return
    }
    
    if (event.key.toLowerCase() === 'a' && !isInputField && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      this.archiveAndNext()
      return
    }
    
    if (event.key.toLowerCase() === 'u' && !isInputField && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      this.undo()
      return
    }
    
    if (event.key === 'Escape') {
      event.preventDefault()
      this.exitTriage()
      return
    }
  }

  private setupKeyboardShortcuts(): void {
    // N = Next document
    const nextSub = this.hotKeyService
      .addShortcut({
        keys: 'n',
        description: $localize`Triage: Next document`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.nextDocument())
    this.shortcutHandlers.push(() => nextSub.unsubscribe())

    // P = Previous document
    const prevSub = this.hotKeyService
      .addShortcut({
        keys: 'p',
        description: $localize`Triage: Previous document`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.previousDocument())
    this.shortcutHandlers.push(() => prevSub.unsubscribe())

    // T = Focus tag input
    const tagSub = this.hotKeyService
      .addShortcut({
        keys: 't',
        description: $localize`Triage: Focus tags`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.focusTagInput())
    this.shortcutHandlers.push(() => tagSub.unsubscribe())

    // C = Focus correspondent input
    const corrSub = this.hotKeyService
      .addShortcut({
        keys: 'c',
        description: $localize`Triage: Focus correspondent`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.focusCorrespondentInput())
    this.shortcutHandlers.push(() => corrSub.unsubscribe())

    // A = Archive / Mark done
    const archiveSub = this.hotKeyService
      .addShortcut({
        keys: 'a',
        description: $localize`Triage: Archive and next`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.archiveAndNext())
    this.shortcutHandlers.push(() => archiveSub.unsubscribe())

    // U = Undo last action
    const undoSub = this.hotKeyService
      .addShortcut({
        keys: 'u',
        description: $localize`Triage: Undo last action`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.undo())
    this.shortcutHandlers.push(() => undoSub.unsubscribe())

    // Escape = Exit triage
    const escSub = this.hotKeyService
      .addShortcut({
        keys: 'escape',
        description: $localize`Triage: Exit`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.exitTriage())
    this.shortcutHandlers.push(() => escSub.unsubscribe())
  }

  private loadCorrespondents(): void {
    this.correspondentService
      .listAll()
      .pipe(first())
      .subscribe((correspondents) => {
        this.correspondents = correspondents.results
      })
  }

  private loadDocumentTypes(): void {
    this.documentTypeService
      .listAll()
      .pipe(first())
      .subscribe((types) => {
        this.documentTypes = types.results
      })
  }

  private loadTags(): void {
    this.tagService
      .listAll()
      .pipe(first())
      .subscribe((tags) => {
        this.tags = tags.results
      })
  }

  private loadCurrentDocument(): void {
    const documentFromQueue = this.triageService.getCurrentDocument()
    if (!documentFromQueue) {
      return
    }

    // Reload document with full permissions to ensure we have the latest data
    // and permissions for saving
    this.documentService
      .get(documentFromQueue.id)
      .pipe(first())
      .subscribe({
        next: (document) => {
          this.currentDocument = document

          // Populate form with current document data
          this.documentForm.patchValue({
            correspondent: document.correspondent,
            document_type: document.document_type,
            tags: document.tags || [],
            created: document.created,
          })

          // Load preview
          this.previewLoaded = false
          this.previewUrl = this.documentService.getPreviewUrl(document.id)
          this.useNativePdfViewer = this.settingsService.get(
            SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER
          )
        },
        error: (error) => {
          console.error('Error loading document:', error)
          this.toastService.showError(
            $localize`Error loading document: ${error?.message || 'Unknown error'}`
          )
        },
      })
  }

  onPdfPreviewLoaded(): void {
    this.previewLoaded = true
  }

  onPdfPreviewError(error: any): void {
    console.error('PDF preview error:', error)
    this.previewLoaded = true
  }

  nextDocument(): void {
    if (this.isSaving) return
    this.triageService.next()
    this.loadCurrentDocument()
  }

  previousDocument(): void {
    if (this.isSaving) return
    this.triageService.previous()
    this.loadCurrentDocument()
  }

  saveCurrentDocument(): void {
    if (!this.currentDocument || this.isSaving) return

    this.isSaving = true

    // Store previous values for undo
    const previousValues: Partial<Document> = {
      correspondent: this.currentDocument.correspondent,
      document_type: this.currentDocument.document_type,
      tags: [...(this.currentDocument.tags || [])],
      created: this.currentDocument.created,
    }

    // Get changed fields
    const changes: Partial<Document> = {
      id: this.currentDocument.id,
    }

    const formValue = this.documentForm.value
    if (formValue.correspondent !== this.currentDocument.correspondent) {
      changes.correspondent = formValue.correspondent ?? null
    }
    if (formValue.document_type !== this.currentDocument.document_type) {
      changes.document_type = formValue.document_type ?? null
    }
    // Compare tags arrays (handle null/undefined and order)
    const formTags = (formValue.tags || []).sort((a, b) => a - b)
    const docTags = (this.currentDocument.tags || []).sort((a, b) => a - b)
    if (JSON.stringify(formTags) !== JSON.stringify(docTags)) {
      changes.tags = formValue.tags || []
    }
    if (formValue.created !== this.currentDocument.created) {
      changes.created = formValue.created ?? null
    }

    // Only save if there are changes
    if (Object.keys(changes).length <= 1) {
      // Only id, no real changes
      this.isSaving = false
      return
    }

    this.documentService
      .patch(changes)
      .pipe(first())
      .subscribe({
        next: (updatedDoc) => {
          this.isSaving = false
          this.toastService.showInfo(
            $localize`Document "${updatedDoc.title}" saved`
          )

          // Push undo action
          this.triageService.pushUndoAction({
            documentId: updatedDoc.id,
            previousValues,
            actionType: 'metadata',
          })

          // Update document in queue
          this.triageService.updateCurrentDocument(updatedDoc)
        },
        error: (error) => {
          this.isSaving = false
          console.error('Error saving document:', error)
          console.error('Error details:', {
            status: error?.status,
            statusText: error?.statusText,
            error: error?.error,
            message: error?.message,
            url: error?.url
          })
          
          let errorMessage = 'Unknown error'
          if (error?.status === 403) {
            // Try to get detailed error from backend
            const backendError = error?.error?.detail || error?.error?.message || error?.error
            if (backendError) {
              errorMessage = typeof backendError === 'string' ? backendError : JSON.stringify(backendError)
            } else {
              errorMessage = 'Permission denied. Your session may have expired. Please try logging out and back in.'
            }
          } else if (error?.status === 400) {
            errorMessage = error?.error?.detail || error?.error?.message || 'Invalid data. Please check your input.'
          } else if (error?.status === 404) {
            errorMessage = 'Document not found.'
          } else if (error?.error?.detail) {
            errorMessage = error.error.detail
          } else if (error?.error?.message) {
            errorMessage = error.error.message
          } else if (error?.message) {
            errorMessage = error.message
          } else if (error?.error) {
            errorMessage = typeof error.error === 'string' ? error.error : JSON.stringify(error.error)
          }
          
          this.toastService.showError(
            $localize`Error saving document: ${errorMessage}`
          )
        },
      })
  }

  saveAndNext(): void {
    if (!this.currentDocument || this.isSaving) return

    // Check if there are changes to save
    const formValue = this.documentForm.value
    const changes: Partial<Document> = {
      id: this.currentDocument.id,
    }

    if (formValue.correspondent !== this.currentDocument.correspondent) {
      changes.correspondent = formValue.correspondent ?? null
    }
    if (formValue.document_type !== this.currentDocument.document_type) {
      changes.document_type = formValue.document_type ?? null
    }
    // Compare tags arrays (handle null/undefined and order)
    const formTags = (formValue.tags || []).sort((a, b) => a - b)
    const docTags = (this.currentDocument.tags || []).sort((a, b) => a - b)
    if (JSON.stringify(formTags) !== JSON.stringify(docTags)) {
      changes.tags = formValue.tags || []
    }
    if (formValue.created !== this.currentDocument.created) {
      changes.created = formValue.created ?? null
    }

    // If no changes, just move to next
    if (Object.keys(changes).length <= 1) {
      this.nextDocument()
      return
    }

    // Save first, then move to next
    this.isSaving = true

    // Store previous values for undo
    const previousValues: Partial<Document> = {
      correspondent: this.currentDocument.correspondent,
      document_type: this.currentDocument.document_type,
      tags: [...(this.currentDocument.tags || [])],
      created: this.currentDocument.created,
    }

    this.documentService
      .patch(changes)
      .pipe(first())
      .subscribe({
        next: (updatedDoc) => {
          this.isSaving = false
          this.toastService.showInfo(
            $localize`Document "${updatedDoc.title}" saved`
          )

          // Push undo action
          this.triageService.pushUndoAction({
            documentId: updatedDoc.id,
            previousValues,
            actionType: 'metadata',
          })

          // Update document in queue
          this.triageService.updateCurrentDocument(updatedDoc)

          // Move to next document after successful save
          this.nextDocument()
        },
        error: (error) => {
          this.isSaving = false
          console.error('Error saving document:', error)
          console.error('Error details:', {
            status: error?.status,
            statusText: error?.statusText,
            error: error?.error,
            message: error?.message,
            url: error?.url
          })
          
          let errorMessage = 'Unknown error'
          if (error?.status === 403) {
            const backendError = error?.error?.detail || error?.error?.message || error?.error
            if (backendError) {
              errorMessage = typeof backendError === 'string' ? backendError : JSON.stringify(backendError)
            } else {
              errorMessage = 'Permission denied. Your session may have expired. Please try logging out and back in.'
            }
          } else if (error?.status === 400) {
            errorMessage = error?.error?.detail || error?.error?.message || 'Invalid data. Please check your input.'
          } else if (error?.status === 404) {
            errorMessage = 'Document not found.'
          } else if (error?.error?.detail) {
            errorMessage = error.error.detail
          } else if (error?.error?.message) {
            errorMessage = error.error.message
          } else if (error?.message) {
            errorMessage = error.message
          } else if (error?.error) {
            errorMessage = typeof error.error === 'string' ? error.error : JSON.stringify(error.error)
          }
          
          this.toastService.showError(
            $localize`Error saving document: ${errorMessage}`
          )
        },
      })
  }

  archiveAndNext(): void {
    if (!this.currentDocument || this.isSaving) return

    this.isSaving = true

    // Store previous values for undo
    const previousValues: Partial<Document> = {
      correspondent: this.currentDocument.correspondent,
      document_type: this.currentDocument.document_type,
      tags: [...(this.currentDocument.tags || [])],
      created: this.currentDocument.created,
    }

    // Build changes from form data
    const changes: Partial<Document> = {
      id: this.currentDocument.id,
    }

    const formValue = this.documentForm.value
    if (formValue.correspondent !== this.currentDocument.correspondent) {
      changes.correspondent = formValue.correspondent ?? null
    }
    if (formValue.document_type !== this.currentDocument.document_type) {
      changes.document_type = formValue.document_type ?? null
    }
    // Compare tags arrays (handle null/undefined and order)
    const formTags = (formValue.tags || []).sort((a, b) => a - b)
    const docTags = (this.currentDocument.tags || []).sort((a, b) => a - b)
    if (JSON.stringify(formTags) !== JSON.stringify(docTags)) {
      changes.tags = formValue.tags || []
    }
    if (formValue.created !== this.currentDocument.created) {
      changes.created = formValue.created ?? null
    }

    // If no changes, just move to next
    if (Object.keys(changes).length === 1) {
      this.isSaving = false
      this.toastService.showInfo($localize`No changes to save`)
      this.triageService.removeCurrentDocument()
      this.loadCurrentDocument()
      return
    }

    this.documentService
      .patch(changes)
      .pipe(first())
      .subscribe({
        next: (updatedDoc) => {
          this.isSaving = false
          this.toastService.showInfo(
            $localize`Document "${updatedDoc.title}" processed`
          )

          // Push undo action
          this.triageService.pushUndoAction({
            documentId: updatedDoc.id,
            previousValues,
            actionType: 'archive',
          })

          // Remove from queue and move to next
          this.triageService.removeCurrentDocument()
          this.loadCurrentDocument()
        },
        error: (error) => {
          this.isSaving = false
          console.error('Error saving document:', error)
          console.error('Error details:', {
            status: error?.status,
            statusText: error?.statusText,
            error: error?.error,
            message: error?.message,
            url: error?.url
          })
          
          let errorMessage = 'Unknown error'
          if (error?.status === 403) {
            // Try to get detailed error from backend
            const backendError = error?.error?.detail || error?.error?.message || error?.error
            if (backendError) {
              errorMessage = typeof backendError === 'string' ? backendError : JSON.stringify(backendError)
            } else {
              errorMessage = 'Permission denied. Your session may have expired. Please try logging out and back in.'
            }
          } else if (error?.status === 400) {
            errorMessage = error?.error?.detail || error?.error?.message || 'Invalid data. Please check your input.'
          } else if (error?.status === 404) {
            errorMessage = 'Document not found.'
          } else if (error?.error?.detail) {
            errorMessage = error.error.detail
          } else if (error?.error?.message) {
            errorMessage = error.error.message
          } else if (error?.message) {
            errorMessage = error.message
          } else if (error?.error) {
            errorMessage = typeof error.error === 'string' ? error.error : JSON.stringify(error.error)
          }
          
          this.toastService.showError(
            $localize`Error saving document: ${errorMessage}`
          )
        },
      })
  }

  undo(): void {
    const lastAction = this.triageService.popUndoAction()
    if (!lastAction) {
      this.toastService.showInfo($localize`Nothing to undo`)
      return
    }

    this.isSaving = true

    // Restore previous values
    const restoreChanges: Partial<Document> = {
      id: lastAction.documentId,
      ...lastAction.previousValues,
    }

    this.documentService
      .patch(restoreChanges)
      .pipe(first())
      .subscribe({
        next: (restoredDoc) => {
          this.isSaving = false
          this.toastService.showInfo($localize`Undo successful`)

          // If it was an archive action, add the document back to the queue
          if (lastAction.actionType === 'archive') {
            const state = this.triageService.getState()
            if (state) {
              state.documents.push(restoredDoc)
              this.triageService.initializeTriage(
                state.documents,
                state.filterRules,
                state.returnUrl
              )
            }
          } else {
            // Update the current document
            this.triageService.updateCurrentDocument(restoredDoc)
            this.loadCurrentDocument()
          }
        },
        error: (error) => {
          this.isSaving = false
          this.toastService.showError($localize`Error undoing action`, error)
          // Push the action back if undo failed
          this.triageService.pushUndoAction(lastAction)
        },
      })
  }

  exitTriage(): void {
    const state = this.triageService.getState()
    const returnUrl = state?.returnUrl || '/documents'
    this.triageService.clear()
    this.router.navigateByUrl(returnUrl)
  }

  private focusTagInput(): void {
    // Focus the tag input element
    const tagInput = document.querySelector('pngx-input-tags input')
    if (tagInput instanceof HTMLElement) {
      tagInput.focus()
    }
  }

  private focusCorrespondentInput(): void {
    // Focus the correspondent input element
    const correspondentInput = document.querySelector(
      'pngx-input-select[title="Correspondent"] input'
    )
    if (correspondentInput instanceof HTMLElement) {
      correspondentInput.focus()
    }
  }

  getRemainingCount(): number {
    return this.triageService.getRemainingCount()
  }

  getCurrentIndex(): number {
    const state = this.triageService.getState()
    return state ? state.currentIndex + 1 : 0
  }

  canUndo(): boolean {
    return this.triageService.canUndo()
  }
}

