import { AsyncPipe, NgTemplateOutlet } from '@angular/common'
import { HttpClient, HttpResponse } from '@angular/common/http'
import { Component, inject, OnDestroy, OnInit, ViewChild } from '@angular/core'
import {
  FormArray,
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import {
  NgbDateStruct,
  NgbDropdownModule,
  NgbModal,
  NgbNav,
  NgbNavChangeEvent,
  NgbNavModule,
} from '@ng-bootstrap/ng-bootstrap'
import { dirtyCheck, DirtyComponent } from '@ngneat/dirty-check-forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { DeviceDetectorService } from 'ngx-device-detector'
import { BehaviorSubject, Observable, of, Subject, timer } from 'rxjs'
import {
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  first,
  map,
  switchMap,
  takeUntil,
  tap,
} from 'rxjs/operators'
import { Correspondent } from 'src/app/data/correspondent'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import { DataType } from 'src/app/data/datatype'
import { Document } from 'src/app/data/document'
import { DocumentMetadata } from 'src/app/data/document-metadata'
import { DocumentNote } from 'src/app/data/document-note'
import { DocumentSuggestions } from 'src/app/data/document-suggestions'
import { DocumentType } from 'src/app/data/document-type'
import { FilterRule } from 'src/app/data/filter-rule'
import {
  FILTER_CORRESPONDENT,
  FILTER_CREATED_AFTER,
  FILTER_CREATED_BEFORE,
  FILTER_DOCUMENT_TYPE,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_HAS_TAGS_ALL,
  FILTER_STORAGE_PATH,
} from 'src/app/data/filter-rule-type'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { User } from 'src/app/data/user'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { ComponentRouterService } from 'src/app/services/component-router.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { HotKeyService } from 'src/app/services/hot-key.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { getFilenameFromContentDisposition } from 'src/app/utils/http'
import { ISODateAdapter } from 'src/app/utils/ngb-iso-date-adapter'
import * as UTIF from 'utif'
import { DocumentDetailFieldID } from '../admin/settings/settings.component'
import { ConfirmDialogComponent } from '../common/confirm-dialog/confirm-dialog.component'
import { PasswordRemovalConfirmDialogComponent } from '../common/confirm-dialog/password-removal-confirm-dialog/password-removal-confirm-dialog.component'
import { CustomFieldsDropdownComponent } from '../common/custom-fields-dropdown/custom-fields-dropdown.component'
import { CorrespondentEditDialogComponent } from '../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { DocumentTypeEditDialogComponent } from '../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { EditDialogMode } from '../common/edit-dialog/edit-dialog.component'
import { StoragePathEditDialogComponent } from '../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { TagEditDialogComponent } from '../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { EmailDocumentDialogComponent } from '../common/email-document-dialog/email-document-dialog.component'
import { CheckComponent } from '../common/input/check/check.component'
import { DateComponent } from '../common/input/date/date.component'
import { DocumentLinkComponent } from '../common/input/document-link/document-link.component'
import { MonetaryComponent } from '../common/input/monetary/monetary.component'
import { NumberComponent } from '../common/input/number/number.component'
import { PermissionsFormComponent } from '../common/input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../common/input/select/select.component'
import { TagsComponent } from '../common/input/tags/tags.component'
import { TextComponent } from '../common/input/text/text.component'
import { TextAreaComponent } from '../common/input/textarea/textarea.component'
import { UrlComponent } from '../common/input/url/url.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { PdfEditorEditMode } from '../common/pdf-editor/pdf-editor-edit-mode'
import { PDFEditorComponent } from '../common/pdf-editor/pdf-editor.component'
import { PngxPdfViewerComponent } from '../common/pdf-viewer/pdf-viewer.component'
import {
  PdfRenderMode,
  PdfSource,
  PdfZoomLevel,
  PdfZoomScale,
  PngxPdfDocumentProxy,
} from '../common/pdf-viewer/pdf-viewer.types'
import { ShareLinksDialogComponent } from '../common/share-links-dialog/share-links-dialog.component'
import { SuggestionsDropdownComponent } from '../common/suggestions-dropdown/suggestions-dropdown.component'
import { DocumentNotesComponent } from '../document-notes/document-notes.component'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { DocumentHistoryComponent } from './document-history/document-history.component'
import { MetadataCollapseComponent } from './metadata-collapse/metadata-collapse.component'

enum DocumentDetailNavIDs {
  Details = 1,
  Content = 2,
  Metadata = 3,
  Preview = 4,
  Notes = 5,
  Permissions = 6,
  History = 7,
  Duplicates = 8,
}

enum ContentRenderType {
  PDF = 'pdf',
  Image = 'image',
  Text = 'text',
  Other = 'other',
  Unknown = 'unknown',
  TIFF = 'tiff',
}

@Component({
  selector: 'pngx-document-detail',
  templateUrl: './document-detail.component.html',
  styleUrls: ['./document-detail.component.scss'],
  imports: [
    PageHeaderComponent,
    CustomFieldsDropdownComponent,
    DocumentNotesComponent,
    DocumentHistoryComponent,
    CheckComponent,
    DateComponent,
    DocumentLinkComponent,
    MetadataCollapseComponent,
    PermissionsFormComponent,
    SelectComponent,
    TagsComponent,
    TextComponent,
    NumberComponent,
    MonetaryComponent,
    UrlComponent,
    SuggestionsDropdownComponent,
    CustomDatePipe,
    FileSizePipe,
    IfPermissionsDirective,
    AsyncPipe,
    FormsModule,
    ReactiveFormsModule,
    NgTemplateOutlet,
    SafeUrlPipe,
    NgbNavModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
    TextAreaComponent,
    RouterModule,
    PngxPdfViewerComponent,
  ],
})
export class DocumentDetailComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy, DirtyComponent
{
  PdfRenderMode = PdfRenderMode
  documentsService = inject(DocumentService)
  private route = inject(ActivatedRoute)
  private tagService = inject(TagService)
  private correspondentService = inject(CorrespondentService)
  private documentTypeService = inject(DocumentTypeService)
  private router = inject(Router)
  private modalService = inject(NgbModal)
  private openDocumentService = inject(OpenDocumentsService)
  private documentListViewService = inject(DocumentListViewService)
  private documentTitlePipe = inject(DocumentTitlePipe)
  private toastService = inject(ToastService)
  private settings = inject(SettingsService)
  private storagePathService = inject(StoragePathService)
  private permissionsService = inject(PermissionsService)
  private userService = inject(UserService)
  private customFieldsService = inject(CustomFieldsService)
  private http = inject(HttpClient)
  private hotKeyService = inject(HotKeyService)
  private componentRouterService = inject(ComponentRouterService)
  private deviceDetectorService = inject(DeviceDetectorService)
  private savedViewService = inject(SavedViewService)

  @ViewChild('inputTitle')
  titleInput: TextComponent

  @ViewChild('tagsInput') tagsInput: TagsComponent

  expandOriginalMetadata = false
  expandArchivedMetadata = false

  error: any

  networkActive = false

  documentId: number
  document: Document
  metadata: DocumentMetadata
  suggestions: DocumentSuggestions
  suggestionsLoading: boolean = false
  users: User[]

  title: string
  titleSubject: Subject<string> = new Subject()
  previewUrl: string
  pdfSource?: PdfSource
  thumbUrl: string
  previewText: string
  previewLoaded: boolean = false
  tiffURL: string
  tiffError: string

  correspondents: Correspondent[]
  documentTypes: DocumentType[]
  storagePaths: StoragePath[]

  documentForm: FormGroup = new FormGroup({
    title: new FormControl(''),
    content: new FormControl(''),
    created: new FormControl(),
    correspondent: new FormControl(),
    document_type: new FormControl(),
    storage_path: new FormControl(),
    archive_serial_number: new FormControl(),
    tags: new FormControl([]),
    permissions_form: new FormControl(null),
    custom_fields: new FormArray([]),
  })

  previewCurrentPage: number = 1
  previewNumPages: number
  previewZoomSetting: PdfZoomLevel = PdfZoomLevel.One
  previewZoomScale: PdfZoomScale = PdfZoomScale.PageWidth

  store: BehaviorSubject<any>
  isDirty$: Observable<boolean>
  unsubscribeNotifier: Subject<any> = new Subject()
  docChangeNotifier: Subject<any> = new Subject()

  requiresPassword: boolean = false
  password: string

  ogDate: Date

  customFields: CustomField[]

  public downloading: boolean = false

  public readonly CustomFieldDataType = CustomFieldDataType

  public readonly ContentRenderType = ContentRenderType

  public readonly DataType = DataType

  public readonly DocumentDetailFieldID = DocumentDetailFieldID

  @ViewChild('nav') nav: NgbNav
  @ViewChild('pdfPreview') set pdfPreview(element) {
    // this gets called when component added or removed from DOM
    if (
      element &&
      element.nativeElement.offsetParent !== null &&
      this.nav?.activeId == DocumentDetailNavIDs.Preview
    ) {
      // its visible
      setTimeout(() => this.nav?.select(DocumentDetailNavIDs.Details))
    }
  }

  DocumentDetailNavIDs = DocumentDetailNavIDs
  activeNavID: number

  titleKeyUp(event) {
    this.titleSubject.next(event.target?.value)
  }

  get useNativePdfViewer(): boolean {
    return this.settings.get(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER)
  }

  get isMobile(): boolean {
    return this.deviceDetectorService.isMobile()
  }

  get aiEnabled(): boolean {
    return this.settings.get(SETTINGS_KEYS.AI_ENABLED)
  }

  get archiveContentRenderType(): ContentRenderType {
    return this.document?.archived_file_name
      ? this.getRenderType('application/pdf')
      : this.getRenderType(this.document?.mime_type)
  }

  get originalContentRenderType(): ContentRenderType {
    return this.getRenderType(this.document?.mime_type)
  }

  get showThumbnailOverlay(): boolean {
    return this.settings.get(SETTINGS_KEYS.DOCUMENT_EDITING_OVERLAY_THUMBNAIL)
  }

  isFieldHidden(fieldId: DocumentDetailFieldID): boolean {
    return this.settings
      .get(SETTINGS_KEYS.DOCUMENT_DETAILS_HIDDEN_FIELDS)
      .includes(fieldId)
  }

  private getRenderType(mimeType: string): ContentRenderType {
    if (!mimeType) return ContentRenderType.Unknown
    if (mimeType === 'application/pdf') {
      return ContentRenderType.PDF
    } else if (
      ['text/plain', 'application/csv', 'text/csv'].includes(mimeType)
    ) {
      return ContentRenderType.Text
    } else if (mimeType.indexOf('tiff') >= 0) {
      return ContentRenderType.TIFF
    } else if (mimeType?.indexOf('image/') === 0) {
      return ContentRenderType.Image
    }
    return ContentRenderType.Other
  }

  private updatePdfSource() {
    if (!this.previewUrl) {
      this.pdfSource = undefined
      return
    }
    this.pdfSource = {
      url: this.previewUrl,
      password: this.password || undefined,
    }
  }

  get isRTL() {
    if (!this.metadata || !this.metadata.lang) return false
    else {
      return ['ar', 'he', 'fe'].includes(this.metadata.lang)
    }
  }

  private mapDocToForm(doc: Document): any {
    return {
      ...doc,
      permissions_form: { owner: doc.owner, set_permissions: doc.permissions },
    }
  }

  private mapFormToDoc(value: any): any {
    const docValues = { ...value }
    docValues['owner'] = value['permissions_form']?.owner
    docValues['set_permissions'] = value['permissions_form']?.set_permissions
    delete docValues['permissions_form']
    return docValues
  }

  private prepareForm(doc: Document): void {
    this.documentForm.reset(this.mapDocToForm(doc), { emitEvent: false })
    if (!this.userCanEditDoc(doc)) {
      this.documentForm.disable({ emitEvent: false })
    } else {
      this.documentForm.enable({ emitEvent: false })
    }
    if (doc.__changedFields) {
      doc.__changedFields.forEach((field) => {
        if (field === 'owner' || field === 'set_permissions') {
          this.documentForm.get('permissions_form')?.markAsDirty()
        } else {
          this.documentForm.get(field)?.markAsDirty()
        }
      })
    }
  }

  private setupDirtyTracking(
    currentDocument: Document,
    originalDocument: Document
  ): void {
    this.store = new BehaviorSubject({
      title: originalDocument.title,
      content: originalDocument.content,
      created: originalDocument.created,
      correspondent: originalDocument.correspondent,
      document_type: originalDocument.document_type,
      storage_path: originalDocument.storage_path,
      archive_serial_number: originalDocument.archive_serial_number,
      tags: [...originalDocument.tags],
      permissions_form: {
        owner: originalDocument.owner,
        set_permissions: originalDocument.permissions,
      },
      custom_fields: [...originalDocument.custom_fields],
    })
    this.isDirty$ = dirtyCheck(this.documentForm, this.store.asObservable())
    this.isDirty$
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe((dirty) =>
        this.openDocumentService.setDirty(
          currentDocument,
          dirty,
          this.getChangedFields()
        )
      )
  }

  private loadDocument(documentId: number): void {
    this.previewUrl = this.documentsService.getPreviewUrl(documentId)
    this.updatePdfSource()
    this.http
      .get(this.previewUrl, { responseType: 'text' })
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe({
        next: (res) => (this.previewText = res.toString()),
        error: (err) =>
          (this.previewText = $localize`An error occurred loading content: ${
            err.message ?? err.toString()
          }`),
      })
    this.thumbUrl = this.documentsService.getThumbUrl(documentId)
    this.documentsService
      .get(documentId)
      .pipe(
        catchError(() => {
          // 404 is handled in the subscribe below
          return of(null)
        }),
        first(),
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe({
        next: (doc) => {
          if (!doc) {
            this.router.navigate(['404'], { replaceUrl: true })
            return
          }
          this.documentId = doc.id
          this.suggestions = null
          const openDocument = this.openDocumentService.getOpenDocument(
            this.documentId
          )
          // update duplicate documents if present
          if (openDocument && doc?.duplicate_documents) {
            openDocument.duplicate_documents = doc.duplicate_documents
            this.openDocumentService.save()
          }
          const useDoc = openDocument || doc
          if (openDocument) {
            if (
              new Date(doc.modified) > new Date(openDocument.modified) &&
              !this.modalService.hasOpenModals()
            ) {
              const modal = this.modalService.open(ConfirmDialogComponent)
              modal.componentInstance.title = $localize`Document changes detected`
              modal.componentInstance.messageBold = $localize`The version of this document in your browser session appears older than the existing version.`
              modal.componentInstance.message = $localize`Saving the document here may overwrite other changes that were made. To restore the existing version, discard your changes or close the document.`
              modal.componentInstance.cancelBtnClass = 'visually-hidden'
              modal.componentInstance.btnCaption = $localize`Ok`
              modal.componentInstance.confirmClicked.subscribe(() =>
                modal.close()
              )
            }
          } else {
            this.openDocumentService
              .openDocument(doc)
              .pipe(
                first(),
                takeUntil(this.unsubscribeNotifier),
                takeUntil(this.docChangeNotifier)
              )
              .subscribe()
          }
          this.updateComponent(useDoc)
          this.titleSubject
            .pipe(
              debounceTime(1000),
              distinctUntilChanged(),
              takeUntil(this.docChangeNotifier),
              takeUntil(this.unsubscribeNotifier)
            )
            .subscribe((titleValue) => {
              if (titleValue !== this.titleInput.value) return
              this.title = titleValue
              this.documentForm.patchValue({ title: titleValue })
              this.documentForm.get('title').markAsDirty()
            })
          this.setupDirtyTracking(useDoc, doc)
        },
      })
  }

  ngOnInit(): void {
    this.setZoom(
      this.settings.get(SETTINGS_KEYS.PDF_VIEWER_ZOOM_SETTING) as PdfZoomScale
    )
    this.documentForm.valueChanges
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((values) => {
        this.error = null
        Object.assign(this.document, this.mapFormToDoc(values))
      })

    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Correspondent
      )
    ) {
      this.correspondentService
        .listAll()
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe((result) => (this.correspondents = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.DocumentType
      )
    ) {
      this.documentTypeService
        .listAll()
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe((result) => (this.documentTypes = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.StoragePath
      )
    ) {
      this.storagePathService
        .listAll()
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe((result) => (this.storagePaths = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.User
      )
    ) {
      this.userService
        .listAll()
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe((result) => (this.users = result.results))
    }

    this.getCustomFields()

    this.route.paramMap
      .pipe(
        filter(
          (paramMap) =>
            +paramMap.get('id') !== this.documentId &&
            paramMap.get('section')?.length > 0
        ),
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe((paramMap) => {
        const documentId = +paramMap.get('id')
        this.docChangeNotifier.next(documentId)
        this.loadDocument(documentId)
      })

    this.route.paramMap
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((paramMap) => {
        const section = paramMap.get('section')
        if (section) {
          const navIDKey: string = Object.keys(DocumentDetailNavIDs).find(
            (navID) => navID.toLowerCase() == section
          )
          if (navIDKey) {
            this.activeNavID = DocumentDetailNavIDs[navIDKey]
          }
        } else if (paramMap.get('id')) {
          this.router.navigate(['documents', +paramMap.get('id'), 'details'], {
            replaceUrl: true,
          })
        }
      })

    this.hotKeyService
      .addShortcut({
        keys: 'control.arrowright',
        description: $localize`Next document`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.hasNext()) this.nextDoc()
      })

    this.hotKeyService
      .addShortcut({
        keys: 'control.arrowleft',
        description: $localize`Previous document`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.hasPrevious()) this.previousDoc()
      })

    this.hotKeyService
      .addShortcut({ keys: 'escape', description: $localize`Close document` })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.close()
      })

    this.hotKeyService
      .addShortcut({ keys: 'control.s', description: $localize`Save document` })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.openDocumentService.isDirty(this.document)) this.save()
      })

    this.hotKeyService
      .addShortcut({
        keys: 'control.shift.s',
        description: $localize`Save and close / next`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.openDocumentService.isDirty(this.document)) {
          if (this.hasNext()) this.saveEditNext()
          else this.save(true)
        }
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  onNavChange(navChangeEvent: NgbNavChangeEvent) {
    const [foundNavIDkey] = Object.entries(DocumentDetailNavIDs).find(
      ([, navIDValue]) => navIDValue == navChangeEvent.nextId
    )
    if (foundNavIDkey)
      this.router.navigate([
        'documents',
        this.documentId,
        foundNavIDkey.toLowerCase(),
      ])
  }

  updateComponent(doc: Document) {
    this.document = doc
    this.requiresPassword = false
    this.updateFormForCustomFields()
    if (this.archiveContentRenderType === ContentRenderType.TIFF) {
      this.tryRenderTiff()
    }
    this.documentsService
      .getMetadata(doc.id)
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe({
        next: (result) => {
          this.metadata = result
          if (
            this.archiveContentRenderType !== ContentRenderType.PDF ||
            this.useNativePdfViewer
          ) {
            this.previewLoaded = true
          }
        },
        error: (error) => {
          this.metadata = {} // allow display to fallback to <object> tag
          this.toastService.showError(
            $localize`Error retrieving metadata`,
            error
          )
        },
      })
    if (
      this.permissionsService.currentUserHasObjectPermissions(
        PermissionAction.Change,
        doc
      ) &&
      this.permissionsService.currentUserCan(
        PermissionAction.Change,
        PermissionType.Document
      )
    ) {
      this.tagService.getCachedMany(doc.tags).subscribe((tags) => {
        // only show suggestions if document has inbox tags
        if (tags.some((tag) => tag.is_inbox_tag)) {
          this.getSuggestions()
        }
      })
    }
    this.title = this.documentTitlePipe.transform(doc.title)
    this.prepareForm(doc)

    if (
      this.activeNavID === DocumentDetailNavIDs.Duplicates &&
      !doc?.duplicate_documents?.length
    ) {
      this.activeNavID = DocumentDetailNavIDs.Details
    }
  }

  get customFieldFormFields(): FormArray {
    return this.documentForm.get('custom_fields') as FormArray
  }

  getSuggestions() {
    this.suggestionsLoading = true
    this.documentsService
      .getSuggestions(this.documentId)
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe({
        next: (result) => {
          this.suggestions = result
          this.suggestionsLoading = false
        },
        error: (error) => {
          this.suggestions = null
          this.suggestionsLoading = false
          this.toastService.showError(
            $localize`Error retrieving suggestions.`,
            error
          )
        },
      })
  }

  createTag(newName: string) {
    var modal = this.modalService.open(TagEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    if (newName) modal.componentInstance.object = { name: newName }
    modal.componentInstance.succeeded
      .pipe(
        tap((newTag: Tag) => {
          // remove from suggestions if present
          if (this.suggestions) {
            this.suggestions = {
              ...this.suggestions,
              suggested_tags: this.suggestions.suggested_tags.filter(
                (tag) => tag !== newTag.name
              ),
            }
          }
        }),
        switchMap((newTag: Tag) => {
          return this.tagService
            .listAll()
            .pipe(map((tags) => ({ newTag, tags })))
        }),
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe(({ newTag, tags }) => {
        this.tagsInput.tags = tags.results
        this.tagsInput.addTag(newTag.id)
      })
  }

  createDocumentType(newName: string) {
    var modal = this.modalService.open(DocumentTypeEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    if (newName) modal.componentInstance.object = { name: newName }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newDocumentType) => {
          return this.documentTypeService
            .listAll()
            .pipe(map((documentTypes) => ({ newDocumentType, documentTypes })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newDocumentType, documentTypes }) => {
        this.documentTypes = documentTypes.results
        this.documentForm.get('document_type').setValue(newDocumentType.id)
        this.documentForm.get('document_type').markAsDirty()
        if (this.suggestions) {
          this.suggestions.suggested_document_types =
            this.suggestions.suggested_document_types.filter(
              (dt) => dt !== newName
            )
        }
      })
  }

  createCorrespondent(newName: string) {
    var modal = this.modalService.open(CorrespondentEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    if (newName) modal.componentInstance.object = { name: newName }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newCorrespondent) => {
          return this.correspondentService
            .listAll()
            .pipe(
              map((correspondents) => ({ newCorrespondent, correspondents }))
            )
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newCorrespondent, correspondents }) => {
        this.correspondents = correspondents.results
        this.documentForm.get('correspondent').setValue(newCorrespondent.id)
        this.documentForm.get('correspondent').markAsDirty()
        if (this.suggestions) {
          this.suggestions.suggested_correspondents =
            this.suggestions.suggested_correspondents.filter(
              (c) => c !== newName
            )
        }
      })
  }

  createStoragePath(newName: string) {
    var modal = this.modalService.open(StoragePathEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    if (newName) modal.componentInstance.object = { name: newName }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newStoragePath) => {
          return this.storagePathService
            .listAll()
            .pipe(map((storagePaths) => ({ newStoragePath, storagePaths })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newStoragePath, storagePaths }) => {
        this.storagePaths = storagePaths.results
        this.documentForm.get('storage_path').setValue(newStoragePath.id)
        this.documentForm.get('storage_path').markAsDirty()
      })
  }

  createDisabled(dataType: DataType) {
    switch (dataType) {
      case DataType.Correspondent:
        return !this.permissionsService.currentUserCan(
          PermissionAction.Add,
          PermissionType.Correspondent
        )
      case DataType.DocumentType:
        return !this.permissionsService.currentUserCan(
          PermissionAction.Add,
          PermissionType.DocumentType
        )
      case DataType.StoragePath:
        return !this.permissionsService.currentUserCan(
          PermissionAction.Add,
          PermissionType.StoragePath
        )
      case DataType.Tag:
        return !this.permissionsService.currentUserCan(
          PermissionAction.Add,
          PermissionType.Tag
        )
    }
  }

  discard() {
    this.documentsService
      .get(this.documentId)
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe({
        next: (doc) => {
          Object.assign(this.document, doc)
          doc['permissions_form'] = {
            owner: doc.owner,
            set_permissions: doc.permissions,
          }
          this.title = doc.title
          this.updateFormForCustomFields()
          this.documentForm.patchValue(doc)
          this.documentForm.markAsPristine()
          this.openDocumentService.setDirty(doc, false)
        },
        error: () => {
          this.router.navigate(['404'], {
            replaceUrl: true,
          })
        },
      })
  }

  private getChangedFields(): any {
    const changes = {
      id: this.document.id,
    }
    Object.keys(this.documentForm.controls).forEach((key) => {
      if (this.documentForm.get(key).dirty) {
        if (key === 'permissions_form') {
          changes['owner'] =
            this.documentForm.get('permissions_form').value['owner']
          changes['set_permissions'] =
            this.documentForm.get('permissions_form').value['set_permissions']
        } else {
          changes[key] = this.documentForm.get(key).value
        }
      }
    })
    return changes
  }

  save(close: boolean = false) {
    this.networkActive = true
    ;(document.activeElement as HTMLElement)?.dispatchEvent(new Event('change'))
    this.documentsService
      .patch(this.getChangedFields())
      .pipe(first())
      .subscribe({
        next: (docValues) => {
          // in case data changed while saving eg removing inbox_tags
          this.documentForm.patchValue(docValues)
          const newValues = Object.assign({}, this.documentForm.value)
          newValues.tags = [...docValues.tags]
          newValues.custom_fields = [...docValues.custom_fields]
          this.store.next(newValues)
          this.openDocumentService.setDirty(this.document, false)
          this.openDocumentService.save()
          this.toastService.showInfo(
            $localize`Document "${newValues.title}" saved successfully.`
          )
          this.networkActive = false
          this.error = null
          if (close) {
            this.close(() =>
              this.openDocumentService.refreshDocument(this.documentId)
            )
          } else {
            this.openDocumentService.refreshDocument(this.documentId)
          }
          this.savedViewService.maybeRefreshDocumentCounts()
        },
        error: (error) => {
          this.networkActive = false
          const canEdit =
            this.permissionsService.currentUserHasObjectPermissions(
              PermissionAction.Change,
              this.document
            )
          if (!canEdit) {
            // document was 'given away'
            this.openDocumentService.setDirty(this.document, false)
            this.toastService.showInfo(
              $localize`Document "${this.document.title}" saved successfully.`
            )
            this.close()
          } else {
            this.error = error.error
            this.toastService.showError(
              $localize`Error saving document "${this.document.title}"`,
              error
            )
          }
        },
      })
  }

  saveEditNext() {
    this.networkActive = true
    this.store.next(this.documentForm.value)
    this.documentsService
      .patch(this.getChangedFields())
      .pipe(
        switchMap((updateResult) => {
          this.savedViewService.maybeRefreshDocumentCounts()
          return this.documentListViewService.getNext(this.documentId).pipe(
            map((nextDocId) => ({ nextDocId, updateResult })),
            takeUntil(this.unsubscribeNotifier)
          )
        })
      )
      .pipe(
        switchMap(({ nextDocId, updateResult }) => {
          if (nextDocId && updateResult) {
            this.openDocumentService.setDirty(this.document, false)
            return this.openDocumentService
              .closeDocument(this.document)
              .pipe(
                map(
                  (closeResult) => ({ updateResult, nextDocId, closeResult }),
                  takeUntil(this.unsubscribeNotifier)
                )
              )
          }
        })
      )
      .pipe(first())
      .subscribe({
        next: ({ updateResult, nextDocId, closeResult }) => {
          this.error = null
          this.networkActive = false
          if (closeResult && updateResult && nextDocId) {
            this.router.navigate(['documents', nextDocId])
            this.titleInput?.focus()
          }
        },
        error: (error) => {
          this.networkActive = false
          this.error = error.error
          this.toastService.showError($localize`Error saving document`, error)
        },
      })
  }

  close(closedCallback: () => void = null) {
    this.openDocumentService
      .closeDocument(this.document)
      .pipe(first())
      .subscribe((closed) => {
        if (!closed) return
        if (closedCallback) closedCallback()
        if (this.documentListViewService.activeSavedViewId) {
          this.router.navigate([
            'view',
            this.documentListViewService.activeSavedViewId,
          ])
        } else if (this.componentRouterService.getComponentURLBefore()) {
          this.router.navigate([
            this.componentRouterService.getComponentURLBefore(),
          ])
        } else {
          this.router.navigate(['documents'])
        }
      })
  }

  delete() {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm`
    modal.componentInstance.messageBold = $localize`Do you really want to move the document "${this.document.title}" to the trash?`
    modal.componentInstance.message = $localize`Documents can be restored prior to permanent deletion.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Move to trash`
    this.subscribeModalDelete(modal) // so can be re-subscribed if error
  }

  subscribeModalDelete(modal) {
    modal.componentInstance.confirmClicked
      .pipe(
        switchMap(() => {
          modal.componentInstance.buttonsEnabled = false
          return this.documentsService.delete(this.document)
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: () => {
          modal.close()
          this.close()
        },
        error: (error) => {
          this.toastService.showError($localize`Error deleting document`, error)
          modal.componentInstance.buttonsEnabled = true
          this.subscribeModalDelete(modal)
        },
      })
  }

  moreLike() {
    this.documentListViewService.quickFilter([
      {
        rule_type: FILTER_FULLTEXT_MORELIKE,
        value: this.documentId.toString(),
      },
    ])
  }

  reprocess() {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Reprocess confirm`
    modal.componentInstance.messageBold = $localize`This operation will permanently recreate the archive file for this document.`
    modal.componentInstance.message = $localize`The archive file will be re-generated with the current settings.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.documentsService
        .bulkEdit([this.document.id], 'reprocess', {})
        .subscribe({
          next: () => {
            this.toastService.showInfo(
              $localize`Reprocess operation for "${this.document.title}" will begin in the background. Close and re-open or reload this document after the operation has completed to see new content.`
            )
            if (modal) {
              modal.close()
            }
          },
          error: (error) => {
            if (modal) {
              modal.componentInstance.buttonsEnabled = true
            }
            this.toastService.showError(
              $localize`Error executing operation`,
              error
            )
          },
        })
    })
  }

  download(original: boolean = false) {
    this.downloading = true
    const downloadUrl = this.documentsService.getDownloadUrl(
      this.documentId,
      original
    )
    this.http
      .get(downloadUrl, { observe: 'response', responseType: 'blob' })
      .subscribe({
        next: (response: HttpResponse<Blob>) => {
          const contentDisposition = response.headers.get('Content-Disposition')
          const filename =
            getFilenameFromContentDisposition(contentDisposition) ||
            this.document.title
          const blob = new Blob([response.body], {
            type: response.body.type,
          })
          this.downloading = false
          const file = new File([blob], filename, {
            type: response.body.type,
          })
          if (
            !this.deviceDetectorService.isDesktop() &&
            navigator.canShare &&
            navigator.canShare({ files: [file] })
          ) {
            navigator.share({
              files: [file],
            })
          } else {
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = filename
            a.click()
            URL.revokeObjectURL(url)
          }
        },
        error: (error) => {
          this.downloading = false
          this.toastService.showError(
            $localize`Error downloading document`,
            error
          )
        },
      })
  }

  hasNext() {
    return this.documentListViewService.hasNext(this.documentId)
  }

  hasPrevious() {
    return this.documentListViewService.hasPrevious(this.documentId)
  }

  nextDoc() {
    this.documentListViewService
      .getNext(this.document.id)
      .subscribe((nextDocId: number) => {
        this.router.navigate(['documents', nextDocId])
      })
  }

  previousDoc() {
    this.documentListViewService
      .getPrevious(this.document.id)
      .subscribe((prevDocId: number) => {
        this.router.navigate(['documents', prevDocId])
      })
  }

  pdfPreviewLoaded(pdf: PngxPdfDocumentProxy) {
    this.previewNumPages = pdf.numPages
    if (this.password) this.requiresPassword = false
    setTimeout(() => {
      this.previewLoaded = true
    }, 300)
  }

  onError(event) {
    if (event.name == 'PasswordException') {
      this.requiresPassword = true
      this.previewLoaded = true
    }
  }

  onPasswordKeyUp(event: KeyboardEvent) {
    if ('Enter' == event.key) {
      this.password = (event.target as HTMLInputElement).value
      this.updatePdfSource()
    }
  }

  setZoom(setting: PdfZoomScale | PdfZoomLevel) {
    if (
      setting === PdfZoomScale.PageFit ||
      setting === PdfZoomScale.PageWidth
    ) {
      this.previewZoomScale = setting
      this.previewZoomSetting = PdfZoomLevel.One
      return
    }
    this.previewZoomSetting = setting
    this.previewZoomScale = PdfZoomScale.PageWidth
  }

  get zoomSettings() {
    return [PdfZoomScale.PageFit, ...Object.values(PdfZoomLevel)]
  }

  get currentZoom() {
    if (this.previewZoomScale === PdfZoomScale.PageFit) {
      return PdfZoomScale.PageFit
    }
    return this.previewZoomSetting
  }

  getZoomSettingTitle(setting: PdfZoomScale | PdfZoomLevel): string {
    switch (setting) {
      case PdfZoomScale.PageFit:
        return $localize`Page Fit`
      default:
        return `${parseFloat(setting) * 100}%`
    }
  }

  increaseZoom(): void {
    const zoomLevels = Object.values(PdfZoomLevel)
    let currentIndex = zoomLevels.indexOf(this.previewZoomSetting)
    if (this.previewZoomScale === PdfZoomScale.PageFit) {
      currentIndex = zoomLevels.indexOf(PdfZoomLevel.One)
    }
    this.previewZoomScale = PdfZoomScale.PageWidth
    this.previewZoomSetting =
      zoomLevels[Math.min(zoomLevels.length - 1, currentIndex + 1)]
  }

  decreaseZoom(): void {
    const zoomLevels = Object.values(PdfZoomLevel)
    let currentIndex = zoomLevels.indexOf(this.previewZoomSetting)
    if (this.previewZoomScale === PdfZoomScale.PageFit) {
      currentIndex = zoomLevels.indexOf(PdfZoomLevel.ThreeQuarters)
    }
    this.previewZoomScale = PdfZoomScale.PageWidth
    this.previewZoomSetting = zoomLevels[Math.max(0, currentIndex - 1)]
  }

  get showPermissions(): boolean {
    return (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.User
      ) && this.userIsOwner
    )
  }

  get notesEnabled(): boolean {
    return (
      this.settings.get(SETTINGS_KEYS.NOTES_ENABLED) &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Note
      )
    )
  }

  get historyEnabled(): boolean {
    return (
      this.settings.get(SETTINGS_KEYS.AUDITLOG_ENABLED) &&
      this.userIsOwner &&
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.History
      )
    )
  }

  notesUpdated(notes: DocumentNote[]) {
    this.document.notes = notes
    this.openDocumentService.refreshDocument(this.documentId)
    this.savedViewService.maybeRefreshDocumentCounts()
  }

  get userIsOwner(): boolean {
    let doc: Document = Object.assign({}, this.document)
    // dont disable while editing
    if (
      this.document &&
      this.store?.value.permissions_form?.hasOwnProperty('owner')
    ) {
      doc.owner = this.store.value.permissions_form.owner
    }
    return !this.document || this.permissionsService.currentUserOwnsObject(doc)
  }

  get userCanEdit(): boolean {
    let doc: Document = Object.assign({}, this.document)
    // dont disable while editing
    if (
      this.document &&
      this.store?.value.permissions_form?.hasOwnProperty('owner')
    ) {
      doc.owner = this.store.value.permissions_form.owner
    }
    return !this.document || this.userCanEditDoc(doc)
  }

  private userCanEditDoc(doc: Document): boolean {
    return (
      this.permissionsService.currentUserCan(
        PermissionAction.Change,
        PermissionType.Document
      ) &&
      this.permissionsService.currentUserHasObjectPermissions(
        PermissionAction.Change,
        doc
      )
    )
  }

  get userCanAdd(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.Add,
      PermissionType.Document
    )
  }

  filterDocuments(items: ObjectWithId[] | NgbDateStruct[], type?: DataType) {
    const filterRules: FilterRule[] = items.flatMap((i) => {
      if (i.hasOwnProperty('year')) {
        const isoDateAdapter = new ISODateAdapter()
        const dateAfter: Date = new Date(isoDateAdapter.toModel(i))
        dateAfter.setDate(dateAfter.getDate() - 1)
        const dateBefore: Date = new Date(isoDateAdapter.toModel(i))
        dateBefore.setDate(dateBefore.getDate() + 1)
        // Created Date
        return [
          {
            rule_type: FILTER_CREATED_AFTER,
            value: dateAfter.toISOString().substring(0, 10),
          },
          {
            rule_type: FILTER_CREATED_BEFORE,
            value: dateBefore.toISOString().substring(0, 10),
          },
        ]
      }
      switch (type) {
        case DataType.Correspondent:
          return {
            rule_type: FILTER_CORRESPONDENT,
            value: (i as Correspondent).id.toString(),
          }
        case DataType.DocumentType:
          return {
            rule_type: FILTER_DOCUMENT_TYPE,
            value: (i as DocumentType).id.toString(),
          }
        case DataType.StoragePath:
          return {
            rule_type: FILTER_STORAGE_PATH,
            value: (i as StoragePath).id.toString(),
          }
        case DataType.Tag:
          return {
            rule_type: FILTER_HAS_TAGS_ALL,
            value: (i as Tag).id.toString(),
          }
      }
    })

    this.documentListViewService.quickFilter(filterRules)
  }

  private getCustomFields() {
    this.customFieldsService
      .listAll()
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => (this.customFields = result.results))
  }

  public refreshCustomFields() {
    this.customFieldsService.clearCache()
    this.getCustomFields()
  }

  public getCustomFieldFromInstance(
    instance: CustomFieldInstance
  ): CustomField {
    return this.customFields?.find((f) => f.id === instance.field)
  }

  public getCustomFieldError(index: number) {
    const fieldError = this.error?.custom_fields?.[index]
    return fieldError?.['non_field_errors'] ?? fieldError?.['value']
  }

  private updateFormForCustomFields(emitEvent: boolean = false) {
    this.customFieldFormFields.clear({ emitEvent: false })
    this.document.custom_fields?.forEach((fieldInstance) => {
      this.customFieldFormFields.push(
        new FormGroup({
          field: new FormControl(fieldInstance.field),
          value: new FormControl(fieldInstance.value),
        }),
        { emitEvent }
      )
    })
  }

  public addField(field: CustomField) {
    this.document.custom_fields.push({
      field: field.id,
      value: null,
      document: this.documentId,
      created: new Date(),
    })
    this.updateFormForCustomFields(true)
    this.documentForm.get('custom_fields').markAsDirty()
    this.documentForm.updateValueAndValidity()
  }

  public removeField(fieldInstance: CustomFieldInstance) {
    this.document.custom_fields.splice(
      this.document.custom_fields.indexOf(fieldInstance),
      1
    )
    this.updateFormForCustomFields(true)
    this.documentForm.get('custom_fields').markAsDirty()
    this.documentForm.updateValueAndValidity()
  }

  editPdf() {
    let modal = this.modalService.open(PDFEditorComponent, {
      backdrop: 'static',
      size: 'xl',
      scrollable: true,
    })
    modal.componentInstance.title = $localize`PDF Editor`
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.documentID = this.document.id
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        this.documentsService
          .bulkEdit([this.document.id], 'edit_pdf', {
            operations: modal.componentInstance.getOperations(),
            delete_original: modal.componentInstance.deleteOriginal,
            update_document:
              modal.componentInstance.editMode == PdfEditorEditMode.Update,
            include_metadata: modal.componentInstance.includeMetadata,
          })
          .pipe(first(), takeUntil(this.unsubscribeNotifier))
          .subscribe({
            next: () => {
              this.toastService.showInfo(
                $localize`PDF edit operation for "${this.document.title}" will begin in the background.`
              )
              modal.close()
              if (modal.componentInstance.deleteOriginal) {
                this.openDocumentService.closeDocument(this.document)
              }
            },
            error: (error) => {
              if (modal) {
                modal.componentInstance.buttonsEnabled = true
              }
              this.toastService.showError(
                $localize`Error executing PDF edit operation`,
                error
              )
            },
          })
      })
  }

  removePassword() {
    if (this.requiresPassword || !this.password) {
      this.toastService.showError(
        $localize`Please enter the current password before attempting to remove it.`
      )
      return
    }
    const modal = this.modalService.open(
      PasswordRemovalConfirmDialogComponent,
      {
        backdrop: 'static',
      }
    )
    modal.componentInstance.title = $localize`Remove password protection`
    modal.componentInstance.message = $localize`Create an unprotected copy or replace the existing file.`
    modal.componentInstance.btnCaption = $localize`Start`

    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        const dialog =
          modal.componentInstance as PasswordRemovalConfirmDialogComponent
        dialog.buttonsEnabled = false
        this.networkActive = true
        this.documentsService
          .bulkEdit([this.document.id], 'remove_password', {
            password: this.password,
            update_document: dialog.updateDocument,
            include_metadata: dialog.includeMetadata,
            delete_original: dialog.deleteOriginal,
          })
          .pipe(first(), takeUntil(this.unsubscribeNotifier))
          .subscribe({
            next: () => {
              this.toastService.showInfo(
                $localize`Password removal operation for "${this.document.title}" will begin in the background.`
              )
              this.networkActive = false
              modal.close()
              if (!dialog.updateDocument && dialog.deleteOriginal) {
                this.openDocumentService.closeDocument(this.document)
              } else if (dialog.updateDocument) {
                this.openDocumentService.refreshDocument(this.documentId)
              }
            },
            error: (error) => {
              dialog.buttonsEnabled = true
              this.networkActive = false
              this.toastService.showError(
                $localize`Error executing password removal operation`,
                error
              )
            },
          })
      })
  }

  printDocument() {
    const printUrl = this.documentsService.getDownloadUrl(
      this.document.id,
      false
    )
    this.http
      .get(printUrl, { responseType: 'blob' })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (blob) => {
          const blobUrl = URL.createObjectURL(blob)
          const iframe = document.createElement('iframe')
          iframe.style.display = 'none'
          iframe.src = blobUrl
          document.body.appendChild(iframe)
          iframe.onload = () => {
            try {
              iframe.contentWindow.focus()
              iframe.contentWindow.print()
              iframe.contentWindow.onafterprint = () => {
                document.body.removeChild(iframe)
                URL.revokeObjectURL(blobUrl)
              }
            } catch (err) {
              // FF throws cross-origin error on onafterprint
              const isCrossOriginAfterPrintError =
                err instanceof DOMException &&
                err.message.includes('onafterprint')
              if (!isCrossOriginAfterPrintError) {
                this.toastService.showError($localize`Print failed.`, err)
              }
              timer(100).subscribe(() => {
                // delay to avoid FF print failure
                document.body.removeChild(iframe)
                URL.revokeObjectURL(blobUrl)
              })
            }
          }
        },
        error: () => {
          this.toastService.showError(
            $localize`Error loading document for printing.`
          )
        },
      })
  }

  public openShareLinks() {
    const modal = this.modalService.open(ShareLinksDialogComponent)
    modal.componentInstance.documentId = this.document.id
    modal.componentInstance.hasArchiveVersion =
      !!this.document?.archived_file_name
  }

  get emailEnabled(): boolean {
    return this.settings.get(SETTINGS_KEYS.EMAIL_ENABLED)
  }

  public openEmailDocument() {
    const modal = this.modalService.open(EmailDocumentDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.documentIds = [this.document.id]
    modal.componentInstance.hasArchiveVersion =
      !!this.document?.archived_file_name
  }

  private tryRenderTiff() {
    this.http
      .get(this.previewUrl, { responseType: 'arraybuffer' })
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        takeUntil(this.docChangeNotifier)
      )
      .subscribe({
        next: (res) => {
          /* istanbul ignore next */
          try {
            // See UTIF.js > _imgLoaded
            const tiffIfds: any[] = UTIF.decode(res)
            var vsns = tiffIfds,
              ma = 0,
              page = vsns[0]
            if (tiffIfds[0].subIFD) vsns = vsns.concat(tiffIfds[0].subIFD)
            for (var i = 0; i < vsns.length; i++) {
              var img = vsns[i]
              if (img['t258'] == null || img['t258'].length < 3) continue
              var ar = img['t256'] * img['t257']
              if (ar > ma) {
                ma = ar
                page = img
              }
            }
            UTIF.decodeImage(res, page, tiffIfds)
            const rgba = UTIF.toRGBA8(page)
            const { width: w, height: h } = page
            var cnv = document.createElement('canvas')
            cnv.width = w
            cnv.height = h
            var ctx = cnv.getContext('2d'),
              imgd = ctx.createImageData(w, h)
            for (var i = 0; i < rgba.length; i++) imgd.data[i] = rgba[i]
            ctx.putImageData(imgd, 0, 0)
            this.tiffURL = cnv.toDataURL()
          } catch (err) {
            this.tiffError = $localize`An error occurred loading tiff: ${err.toString()}`
          }
        },
        error: (err) => {
          this.tiffError = $localize`An error occurred loading tiff: ${err.toString()}`
        },
      })
  }
}
