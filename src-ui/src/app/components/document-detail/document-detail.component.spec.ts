import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  ActivatedRoute,
  Router,
  RouterModule,
  convertToParamMap,
} from '@angular/router'
import {
  NgbDateStruct,
  NgbModal,
  NgbModalModule,
  NgbModalRef,
  NgbModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { PdfViewerModule } from 'ng2-pdf-viewer'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { Correspondent } from 'src/app/data/correspondent'
import { CustomFieldDataType } from 'src/app/data/custom-field'
import { DataType } from 'src/app/data/datatype'
import { Document } from 'src/app/data/document'
import { DocumentType } from 'src/app/data/document-type'
import {
  FILTER_CORRESPONDENT,
  FILTER_CREATED_AFTER,
  FILTER_CREATED_BEFORE,
  FILTER_DOCUMENT_TYPE,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_HAS_TAGS_ALL,
  FILTER_STORAGE_PATH,
} from 'src/app/data/filter-rule-type'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../common/confirm-dialog/confirm-dialog.component'
import { DeletePagesConfirmDialogComponent } from '../common/confirm-dialog/delete-pages-confirm-dialog/delete-pages-confirm-dialog.component'
import { RotateConfirmDialogComponent } from '../common/confirm-dialog/rotate-confirm-dialog/rotate-confirm-dialog.component'
import { SplitConfirmDialogComponent } from '../common/confirm-dialog/split-confirm-dialog/split-confirm-dialog.component'
import { CustomFieldsDropdownComponent } from '../common/custom-fields-dropdown/custom-fields-dropdown.component'
import { CorrespondentEditDialogComponent } from '../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { DocumentTypeEditDialogComponent } from '../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { StoragePathEditDialogComponent } from '../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { DateComponent } from '../common/input/date/date.component'
import { NumberComponent } from '../common/input/number/number.component'
import { PermissionsFormComponent } from '../common/input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../common/input/select/select.component'
import { TagsComponent } from '../common/input/tags/tags.component'
import { TextComponent } from '../common/input/text/text.component'
import { TextAreaComponent } from '../common/input/textarea/textarea.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { ShareLinksDropdownComponent } from '../common/share-links-dropdown/share-links-dropdown.component'
import { DocumentNotesComponent } from '../document-notes/document-notes.component'
import { DocumentDetailComponent } from './document-detail.component'

const doc: Document = {
  id: 3,
  title: 'Doc 3',
  correspondent: 11,
  document_type: 21,
  storage_path: 31,
  tags: [41, 42, 43],
  content: 'text content',
  added: new Date('May 4, 2014 03:24:00'),
  created: new Date('May 4, 2014 03:24:00'),
  modified: new Date('May 4, 2014 03:24:00'),
  archive_serial_number: null,
  original_file_name: 'file.pdf',
  owner: null,
  user_can_change: true,
  notes: [
    {
      created: new Date(),
      note: 'note 1',
      user: { id: 1, username: 'user1' },
    },
    {
      created: new Date(),
      note: 'note 2',
      user: { id: 2, username: 'user2' },
    },
  ],
  custom_fields: [
    {
      field: 0,
      document: 3,
      created: new Date(),
      value: 'custom foo bar',
    },
  ],
}

const customFields = [
  {
    id: 0,
    name: 'Field 1',
    data_type: CustomFieldDataType.String,
    created: new Date(),
  },
  {
    id: 1,
    name: 'Custom Field 2',
    data_type: CustomFieldDataType.Integer,
    created: new Date(),
  },
]

describe('DocumentDetailComponent', () => {
  let component: DocumentDetailComponent
  let fixture: ComponentFixture<DocumentDetailComponent>
  let router: Router
  let activatedRoute: ActivatedRoute
  let documentService: DocumentService
  let openDocumentsService: OpenDocumentsService
  let modalService: NgbModal
  let toastService: ToastService
  let documentListViewService: DocumentListViewService
  let settingsService: SettingsService
  let customFieldsService: CustomFieldsService
  let httpTestingController: HttpTestingController

  let currentUserCan = true
  let currentUserHasObjectPermissions = true
  let currentUserOwnsObject = true

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DocumentDetailComponent,
        DocumentTitlePipe,
        PageHeaderComponent,
        IfPermissionsDirective,
        TagsComponent,
        SelectComponent,
        TextComponent,
        NumberComponent,
        DateComponent,
        DocumentNotesComponent,
        CustomDatePipe,
        DocumentTypeEditDialogComponent,
        CorrespondentEditDialogComponent,
        StoragePathEditDialogComponent,
        IfOwnerDirective,
        PermissionsFormComponent,
        SafeHtmlPipe,
        ConfirmDialogComponent,
        SafeUrlPipe,
        ShareLinksDropdownComponent,
        CustomFieldsDropdownComponent,
        SplitConfirmDialogComponent,
        RotateConfirmDialogComponent,
        DeletePagesConfirmDialogComponent,
        TextAreaComponent,
      ],
      imports: [
        RouterModule.forRoot(routes),
        NgbModule,
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        NgxBootstrapIconsModule.pick(allIcons),
        PdfViewerModule,
      ],
      providers: [
        DocumentTitlePipe,
        {
          provide: TagService,
          useValue: {
            listAll: () =>
              of({
                count: 3,
                all: [41, 42, 43],
                results: [
                  {
                    id: 41,
                    name: 'Tag41',
                    is_inbox_tag: true,
                    color: '#ff0000',
                    text_color: '#000000',
                  },
                  {
                    id: 42,
                    name: 'Tag42',
                    is_inbox_tag: true,
                    color: '#ff0000',
                    text_color: '#000000',
                  },
                  {
                    id: 43,
                    name: 'Tag43',
                    is_inbox_tag: true,
                    color: '#ff0000',
                    text_color: '#000000',
                  },
                ],
              }),
          },
        },
        {
          provide: CorrespondentService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 11,
                    name: 'Correspondent11',
                  },
                ],
              }),
          },
        },
        {
          provide: DocumentTypeService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 21,
                    name: 'DocumentType21',
                  },
                ],
              }),
          },
        },
        {
          provide: StoragePathService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 31,
                    name: 'StoragePath31',
                  },
                ],
              }),
          },
        },
        {
          provide: UserService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    username: 'user1',
                  },
                  {
                    id: 2,
                    username: 'user2',
                  },
                ],
              }),
          },
        },
        CustomFieldsService,
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => currentUserCan,
            currentUserHasObjectPermissions: () =>
              currentUserHasObjectPermissions,
            currentUserOwnsObject: () => currentUserOwnsObject,
          },
        },
        PermissionsGuard,
        CustomDatePipe,
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    router = TestBed.inject(Router)
    activatedRoute = TestBed.inject(ActivatedRoute)
    openDocumentsService = TestBed.inject(OpenDocumentsService)
    documentService = TestBed.inject(DocumentService)
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)
    documentListViewService = TestBed.inject(DocumentListViewService)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 1 }
    customFieldsService = TestBed.inject(CustomFieldsService)
    fixture = TestBed.createComponent(DocumentDetailComponent)
    httpTestingController = TestBed.inject(HttpTestingController)
    component = fixture.componentInstance
  })

  it('should load four tabs via url params', () => {
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: 3, section: 'notes' })))
    jest.spyOn(openDocumentsService, 'getOpenDocument').mockReturnValue(null)
    jest
      .spyOn(openDocumentsService, 'openDocument')
      .mockReturnValueOnce(of(true))
    fixture.detectChanges()
    expect(component.activeNavID).toEqual(5) // DocumentDetailNavIDs.Notes
  })

  it('should change url on tab switch', () => {
    initNormally()
    const navigateSpy = jest.spyOn(router, 'navigate')
    component.nav.select(5)
    component.nav.navChange.next({
      activeId: 1,
      nextId: 5,
      preventDefault: () => {},
    })
    fixture.detectChanges()
    expect(navigateSpy).toHaveBeenCalledWith(['documents', 3, 'notes'])
  })

  it('should forward id without section to details', () => {
    const navigateSpy = jest.spyOn(router, 'navigate')
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: 3 })))
    fixture.detectChanges()
    expect(navigateSpy).toHaveBeenCalledWith(['documents', 3, 'details'], {
      replaceUrl: true,
    })
  })

  it('should update title after debounce', fakeAsync(() => {
    initNormally()
    component.titleInput.value = 'Foo Bar'
    component.titleSubject.next('Foo Bar')
    tick(1000)
    expect(component.documentForm.get('title').value).toEqual('Foo Bar')
    discardPeriodicTasks()
  }))

  it('should update title before doc change if was not updated via debounce', fakeAsync(() => {
    initNormally()
    component.titleInput.value = 'Foo Bar'
    component.titleInput.inputField.nativeElement.dispatchEvent(
      new Event('change')
    )
    tick(1000)
    expect(component.documentForm.get('title').value).toEqual('Foo Bar')
  }))

  it('should load non-open document via param', () => {
    initNormally()
    expect(component.document).toEqual(doc)
  })

  it('should load already-opened document via param', () => {
    initNormally()
    jest.spyOn(documentService, 'get').mockReturnValueOnce(of(doc))
    jest.spyOn(openDocumentsService, 'getOpenDocument').mockReturnValue(doc)
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        count: customFields.length,
        all: customFields.map((f) => f.id),
        results: customFields,
      })
    )
    fixture.detectChanges() // calls ngOnInit
    expect(component.document).toEqual(doc)
  })

  it('should disable form if user cannot edit', () => {
    currentUserHasObjectPermissions = false
    initNormally()
    expect(component.documentForm.disabled).toBeTruthy()
  })

  it('should not attempt to retrieve objects if user does not have permissions', () => {
    currentUserCan = false
    initNormally()
    expect(component.correspondents).toBeUndefined()
    expect(component.documentTypes).toBeUndefined()
    expect(component.storagePaths).toBeUndefined()
    expect(component.users).toBeUndefined()
    httpTestingController.expectNone(`${environment.apiBaseUrl}documents/tags/`)
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/correspondents/`
    )
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/document_types/`
    )
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/storage_paths/`
    )
    currentUserCan = true
  })

  it('should support creating document type', () => {
    initNormally()
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    component.createDocumentType('NewDocType2')
    expect(modalSpy).toHaveBeenCalled()
    openModal.componentInstance.succeeded.next({ id: 12, name: 'NewDocType12' })
    expect(component.documentForm.get('document_type').value).toEqual(12)
  })

  it('should support creating correspondent', () => {
    initNormally()
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    component.createCorrespondent('NewCorrrespondent12')
    expect(modalSpy).toHaveBeenCalled()
    openModal.componentInstance.succeeded.next({
      id: 12,
      name: 'NewCorrrespondent12',
    })
    expect(component.documentForm.get('correspondent').value).toEqual(12)
  })

  it('should support creating storage path', () => {
    initNormally()
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    component.createStoragePath('NewStoragePath12')
    expect(modalSpy).toHaveBeenCalled()
    openModal.componentInstance.succeeded.next({
      id: 12,
      name: 'NewStoragePath12',
    })
    expect(component.documentForm.get('storage_path').value).toEqual(12)
  })

  it('should allow dischard changes', () => {
    initNormally()
    component.title = 'Foo Bar'
    fixture.detectChanges()
    jest.spyOn(documentService, 'get').mockReturnValueOnce(of(doc))
    component.discard()
    fixture.detectChanges()
    expect(component.title).toEqual(doc.title)
    expect(openDocumentsService.hasDirty()).toBeFalsy()
    // this time with error, mostly for coverage
    component.title = 'Foo Bar'
    fixture.detectChanges()
    const navigateSpy = jest.spyOn(router, 'navigate')
    jest
      .spyOn(documentService, 'get')
      .mockReturnValueOnce(throwError(() => new Error('unable to discard')))
    component.discard()
    fixture.detectChanges()
    expect(navigateSpy).toHaveBeenCalledWith(['404'], { replaceUrl: true })
  })

  it('should 404 on invalid id', () => {
    const navigateSpy = jest.spyOn(router, 'navigate')
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: 999, section: 'details' })))
    jest.spyOn(documentService, 'get').mockReturnValueOnce(of(null))
    fixture.detectChanges()
    expect(navigateSpy).toHaveBeenCalledWith(['404'], { replaceUrl: true })
  })

  it('should support save, close and show success toast', () => {
    initNormally()
    component.title = 'Foo Bar'
    const closeSpy = jest.spyOn(component, 'close')
    const updateSpy = jest.spyOn(documentService, 'update')
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    updateSpy.mockImplementation((o) => of(doc))
    component.save(true)
    expect(updateSpy).toHaveBeenCalled()
    expect(closeSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith('Document saved successfully.')
  })

  it('should support save without close and show success toast', () => {
    initNormally()
    component.title = 'Foo Bar'
    const closeSpy = jest.spyOn(component, 'close')
    const updateSpy = jest.spyOn(documentService, 'update')
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    updateSpy.mockImplementation((o) => of(doc))
    component.save()
    expect(updateSpy).toHaveBeenCalled()
    expect(closeSpy).not.toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith('Document saved successfully.')
  })

  it('should show toast error on save if error occurs', () => {
    currentUserHasObjectPermissions = true
    initNormally()
    component.title = 'Foo Bar'
    const closeSpy = jest.spyOn(component, 'close')
    const updateSpy = jest.spyOn(documentService, 'update')
    const toastSpy = jest.spyOn(toastService, 'showError')
    const error = new Error('failed to save')
    updateSpy.mockImplementation(() => throwError(() => error))
    component.save()
    expect(updateSpy).toHaveBeenCalled()
    expect(closeSpy).not.toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith('Error saving document', error)
  })

  it('should show error toast on save but close if user can no longer edit', () => {
    currentUserHasObjectPermissions = false
    initNormally()
    component.title = 'Foo Bar'
    const closeSpy = jest.spyOn(component, 'close')
    const updateSpy = jest.spyOn(documentService, 'update')
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    updateSpy.mockImplementation(() =>
      throwError(() => new Error('failed to save'))
    )
    component.save(true)
    expect(updateSpy).toHaveBeenCalled()
    expect(closeSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith('Document saved successfully.')
  })

  it('should allow save and next', () => {
    initNormally()
    const nextDocId = 100
    component.title = 'Foo Bar'
    const updateSpy = jest.spyOn(documentService, 'update')
    updateSpy.mockReturnValue(of(doc))
    const nextSpy = jest.spyOn(documentListViewService, 'getNext')
    nextSpy.mockReturnValue(of(nextDocId))
    const closeSpy = jest.spyOn(openDocumentsService, 'closeDocument')
    closeSpy.mockReturnValue(of(true))
    const navigateSpy = jest.spyOn(router, 'navigate')

    component.saveEditNext()
    expect(updateSpy).toHaveBeenCalled()
    expect(navigateSpy).toHaveBeenCalledWith(['documents', nextDocId])
    expect
  })

  it('should show toast error on save & next if error occurs', () => {
    currentUserHasObjectPermissions = true
    initNormally()
    component.title = 'Foo Bar'
    const closeSpy = jest.spyOn(component, 'close')
    const updateSpy = jest.spyOn(documentService, 'update')
    const toastSpy = jest.spyOn(toastService, 'showError')
    const error = new Error('failed to save')
    updateSpy.mockImplementation(() => throwError(() => error))
    component.saveEditNext()
    expect(updateSpy).toHaveBeenCalled()
    expect(closeSpy).not.toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith('Error saving document', error)
  })

  it('should show save button and save & close or save & next', () => {
    const nextSpy = jest.spyOn(component, 'hasNext')
    nextSpy.mockReturnValueOnce(false)
    fixture.detectChanges()
    expect(
      fixture.debugElement
        .queryAll(By.css('button'))
        .find((b) => b.nativeElement.textContent === 'Save')
    ).not.toBeUndefined()
    expect(
      fixture.debugElement
        .queryAll(By.css('button'))
        .find((b) => b.nativeElement.textContent === 'Save & close')
    ).not.toBeUndefined()
    expect(
      fixture.debugElement
        .queryAll(By.css('button'))
        .find((b) => b.nativeElement.textContent === 'Save & next')
    ).toBeUndefined()
    nextSpy.mockReturnValue(true)
    fixture.detectChanges()
    expect(
      fixture.debugElement
        .queryAll(By.css('button'))
        .find((b) => b.nativeElement.textContent === 'Save & close')
    ).toBeUndefined()
    expect(
      fixture.debugElement
        .queryAll(By.css('button'))
        .find((b) => b.nativeElement.textContent === 'Save & next')
    ).not.toBeUndefined()
  })

  it('should allow close and navigate to documents by default', () => {
    initNormally()
    const navigateSpy = jest.spyOn(router, 'navigate')
    component.close()
    expect(navigateSpy).toHaveBeenCalledWith(['documents'])
  })

  it('should allow close and navigate to documents by default', () => {
    initNormally()
    jest
      .spyOn(documentListViewService, 'activeSavedViewId', 'get')
      .mockReturnValue(77)
    const navigateSpy = jest.spyOn(router, 'navigate')
    component.close()
    expect(navigateSpy).toHaveBeenCalledWith(['view', 77])
  })

  it('should not close if e.g. user-cancelled', () => {
    initNormally()
    jest.spyOn(openDocumentsService, 'closeDocument').mockReturnValue(of(false))
    const navigateSpy = jest.spyOn(router, 'navigate')
    component.close()
    expect(navigateSpy).not.toHaveBeenCalled()
  })

  it('should support delete, ask for confirmation', () => {
    initNormally()
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    const deleteSpy = jest.spyOn(documentService, 'delete')
    deleteSpy.mockReturnValue(of(true))
    component.delete()
    expect(modalSpy).toHaveBeenCalled()
    const modalCloseSpy = jest.spyOn(openModal, 'close')
    openModal.componentInstance.confirmClicked.next()
    expect(deleteSpy).toHaveBeenCalled()
    expect(modalCloseSpy).toHaveBeenCalled()
  })

  it('should allow retry delete if error', () => {
    initNormally()
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    const deleteSpy = jest.spyOn(documentService, 'delete')
    deleteSpy.mockReturnValueOnce(throwError(() => new Error('one time')))
    component.delete()
    expect(modalSpy).toHaveBeenCalled()
    const modalCloseSpy = jest.spyOn(openModal, 'close')
    openModal.componentInstance.confirmClicked.next()
    expect(deleteSpy).toHaveBeenCalled()
    expect(modalCloseSpy).not.toHaveBeenCalled()
    deleteSpy.mockReturnValueOnce(of(true))
    // retry
    openModal.componentInstance.confirmClicked.next()
    expect(deleteSpy).toHaveBeenCalled()
    expect(modalCloseSpy).toHaveBeenCalled()
  })

  it('should support more like quick filter', () => {
    initNormally()
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.moreLike()
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_FULLTEXT_MORELIKE,
        value: doc.id.toString(),
      },
    ])
  })

  it('should support reprocess, confirm and close modal after started', () => {
    initNormally()
    const bulkEditSpy = jest.spyOn(documentService, 'bulkEdit')
    bulkEditSpy.mockReturnValue(of(true))
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    component.reprocess()
    const modalCloseSpy = jest.spyOn(openModal, 'close')
    openModal.componentInstance.confirmClicked.next()
    expect(bulkEditSpy).toHaveBeenCalledWith([doc.id], 'reprocess', {})
    expect(modalSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalled()
    expect(modalCloseSpy).toHaveBeenCalled()
  })

  it('should show error if redo ocr call fails', () => {
    initNormally()
    const bulkEditSpy = jest.spyOn(documentService, 'bulkEdit')
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modal) => (openModal = modal[0]))
    const toastSpy = jest.spyOn(toastService, 'showError')
    component.reprocess()
    const modalCloseSpy = jest.spyOn(openModal, 'close')
    bulkEditSpy.mockReturnValue(throwError(() => new Error('error occurred')))
    openModal.componentInstance.confirmClicked.next()
    expect(toastSpy).toHaveBeenCalled()
    expect(modalCloseSpy).not.toHaveBeenCalled()
  })

  it('should support next doc', () => {
    initNormally()
    const serviceSpy = jest.spyOn(documentListViewService, 'getNext')
    const routerSpy = jest.spyOn(router, 'navigate')
    serviceSpy.mockReturnValue(of(100))
    component.nextDoc()
    expect(serviceSpy).toHaveBeenCalled()
    expect(routerSpy).toHaveBeenCalledWith(['documents', 100])
  })

  it('should support previous doc', () => {
    initNormally()
    const serviceSpy = jest.spyOn(documentListViewService, 'getPrevious')
    const routerSpy = jest.spyOn(router, 'navigate')
    serviceSpy.mockReturnValue(of(100))
    component.previousDoc()
    expect(serviceSpy).toHaveBeenCalled()
    expect(routerSpy).toHaveBeenCalledWith(['documents', 100])
  })

  it('should support password-protected PDFs with a password field', () => {
    initNormally()
    component.onError({ name: 'PasswordException' }) // normally dispatched by pdf viewer
    expect(component.requiresPassword).toBeTruthy()
    fixture.detectChanges()
    expect(
      fixture.debugElement.query(By.css('input[type=password]'))
    ).not.toBeUndefined()
    component.password = 'foo'
    component.pdfPreviewLoaded({ numPages: 1000 } as any)
    expect(component.requiresPassword).toBeFalsy()
  })

  it('should support Enter key in password field', () => {
    initNormally()
    component.metadata = { has_archive_version: true }
    component.onError({ name: 'PasswordException' }) // normally dispatched by pdf viewer
    fixture.detectChanges()
    expect(component.password).toBeUndefined()
    const pwField = fixture.debugElement.query(By.css('input[type=password]'))
    pwField.nativeElement.value = 'foobar'
    pwField.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Enter' })
    )
    expect(component.password).toEqual('foobar')
  })

  it('should update n pages after pdf loaded', () => {
    initNormally()
    component.pdfPreviewLoaded({ numPages: 1000 } as any)
    expect(component.previewNumPages).toEqual(1000)
  })

  it('should include delay of 300ms after previewloaded before showing pdf', fakeAsync(() => {
    initNormally()
    expect(component.previewLoaded).toBeFalsy()
    component.pdfPreviewLoaded({ numPages: 1000 } as any)
    expect(component.previewNumPages).toEqual(1000)
    tick(300)
    expect(component.previewLoaded).toBeTruthy()
  }))

  it('should support zoom controls', () => {
    initNormally()
    component.onZoomSelect({ target: { value: '1' } } as any) // from select
    expect(component.previewZoomSetting).toEqual('1')
    component.increaseZoom()
    expect(component.previewZoomSetting).toEqual('1.5')
    component.increaseZoom()
    expect(component.previewZoomSetting).toEqual('2')
    component.decreaseZoom()
    expect(component.previewZoomSetting).toEqual('1.5')
    component.onZoomSelect({ target: { value: '1' } } as any) // from select
    component.decreaseZoom()
    expect(component.previewZoomSetting).toEqual('.75')

    component.onZoomSelect({ target: { value: 'page-fit' } } as any) // from select
    expect(component.previewZoomScale).toEqual('page-fit')
    expect(component.previewZoomSetting).toEqual('1')
    component.increaseZoom()
    expect(component.previewZoomSetting).toEqual('1.5')
    expect(component.previewZoomScale).toEqual('page-width')

    component.onZoomSelect({ target: { value: 'page-fit' } } as any) // from select
    expect(component.previewZoomScale).toEqual('page-fit')
    expect(component.previewZoomSetting).toEqual('1')
    component.decreaseZoom()
    expect(component.previewZoomSetting).toEqual('.5')
    expect(component.previewZoomScale).toEqual('page-width')
  })

  it('should support updating notes dynamically', () => {
    const notes = [
      {
        id: 1,
        note: 'hello world',
      },
    ]
    initNormally()
    const refreshSpy = jest.spyOn(openDocumentsService, 'refreshDocument')
    component.notesUpdated(notes) // called by notes component
    expect(component.document.notes).toEqual(notes)
    expect(refreshSpy).toHaveBeenCalled()
  })

  it('should support quick filtering by correspondent', () => {
    initNormally()
    const object = {
      id: 22,
      name: 'Correspondent22',
    } as Correspondent
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.filterDocuments([object], DataType.Correspondent)
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_CORRESPONDENT,
        value: object.id.toString(),
      },
    ])
  })

  it('should support quick filtering by doc type', () => {
    initNormally()
    const object = { id: 22, name: 'DocumentType22' } as DocumentType
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.filterDocuments([object], DataType.DocumentType)
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_DOCUMENT_TYPE,
        value: object.id.toString(),
      },
    ])
  })

  it('should support quick filtering by storage path', () => {
    initNormally()
    const object = {
      id: 22,
      name: 'StoragePath22',
      path: '/foo/bar/',
    } as StoragePath
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.filterDocuments([object], DataType.StoragePath)
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_STORAGE_PATH,
        value: object.id.toString(),
      },
    ])
  })

  it('should support quick filtering by all tags', () => {
    initNormally()
    const object1 = {
      id: 22,
      name: 'Tag22',
      is_inbox_tag: true,
      color: '#ff0000',
      text_color: '#000000',
    } as Tag
    const object2 = {
      id: 23,
      name: 'Tag22',
      is_inbox_tag: true,
      color: '#ff0000',
      text_color: '#000000',
    } as Tag
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.filterDocuments([object1, object2], DataType.Tag)
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: object1.id.toString(),
      },
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: object2.id.toString(),
      },
    ])
  })

  it('should support quick filtering by date after - 1d and before +1d', () => {
    initNormally()
    const object = { year: 2023, month: 5, day: 14 } as NgbDateStruct
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    component.filterDocuments([object])
    expect(qfSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_CREATED_AFTER,
        value: '2023-05-13',
      },
      {
        rule_type: FILTER_CREATED_BEFORE,
        value: '2023-05-15',
      },
    ])
  })

  it('should detect RTL languages and add css class to content textarea', () => {
    initNormally()
    component.metadata = { lang: 'he' }
    component.nav.select(2) // content
    fixture.detectChanges()
    expect(component.isRTL).toBeTruthy()
    expect(fixture.debugElement.queryAll(By.css('textarea.rtl'))).not.toBeNull()
  })

  it('should display built-in pdf viewer if not disabled', () => {
    initNormally()
    component.document.archived_file_name = 'file.pdf'
    jest.spyOn(settingsService, 'get').mockReturnValue(false)
    expect(component.useNativePdfViewer).toBeFalsy()
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('pdf-viewer'))).not.toBeNull()
  })

  it('should display native pdf viewer if enabled', () => {
    initNormally()
    component.document.archived_file_name = 'file.pdf'
    jest.spyOn(settingsService, 'get').mockReturnValue(true)
    expect(component.useNativePdfViewer).toBeTruthy()
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).not.toBeNull()
  })

  it('should attempt to retrieve metadata', () => {
    const metadataSpy = jest.spyOn(documentService, 'getMetadata')
    metadataSpy.mockReturnValue(of({ has_archive_version: true }))
    initNormally()
    expect(metadataSpy).toHaveBeenCalled()
  })

  it('should show an error if failed metadata retrieval', () => {
    const error = new Error('metadata error')
    jest
      .spyOn(documentService, 'getMetadata')
      .mockReturnValue(throwError(() => error))
    const toastSpy = jest.spyOn(toastService, 'showError')
    initNormally()
    expect(toastSpy).toHaveBeenCalledWith('Error retrieving metadata', error)
  })

  it('should display custom fields', () => {
    initNormally()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      customFields[0].name
    )
  })

  it('should support add custom field, correctly send via post', () => {
    initNormally()
    const initialLength = doc.custom_fields.length
    expect(component.customFieldFormFields).toHaveLength(initialLength)
    component.addField(customFields[1])
    fixture.detectChanges()
    expect(component.document.custom_fields).toHaveLength(initialLength + 1)
    expect(component.customFieldFormFields).toHaveLength(initialLength + 1)
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      customFields[1].name
    )
    const updateSpy = jest.spyOn(documentService, 'update')
    component.save(true)
    expect(updateSpy.mock.lastCall[0].custom_fields).toHaveLength(2)
    expect(updateSpy.mock.lastCall[0].custom_fields[1]).toEqual({
      field: customFields[1].id,
      value: null,
    })
  })

  it('should support remove custom field, correctly send via post', () => {
    initNormally()
    const initialLength = doc.custom_fields.length
    expect(component.customFieldFormFields).toHaveLength(initialLength)
    component.removeField(doc.custom_fields[0])
    fixture.detectChanges()
    expect(component.document.custom_fields).toHaveLength(initialLength - 1)
    expect(component.customFieldFormFields).toHaveLength(initialLength - 1)
    expect(
      fixture.debugElement.query(By.css('form')).nativeElement.textContent
    ).not.toContain('Field 1')
    const updateSpy = jest.spyOn(documentService, 'update')
    component.save(true)
    expect(updateSpy.mock.lastCall[0].custom_fields).toHaveLength(
      initialLength - 1
    )
  })

  it('should show custom field errors', () => {
    initNormally()
    component.error = {
      custom_fields: [
        {},
        {},
        { value: ['This field may not be null.'] },
        {},
        { non_field_errors: ['Enter a valid URL.'] },
      ],
    }
    expect(component.getCustomFieldError(2)).toEqual([
      'This field may not be null.',
    ])
    expect(component.getCustomFieldError(4)).toEqual(['Enter a valid URL.'])
  })

  it('should refresh custom fields when created', () => {
    initNormally()
    const refreshSpy = jest.spyOn(component, 'refreshCustomFields')
    fixture.debugElement
      .query(By.directive(CustomFieldsDropdownComponent))
      .triggerEventHandler('created')
    expect(refreshSpy).toHaveBeenCalled()
  })

  it('should get suggestions', () => {
    const suggestionsSpy = jest.spyOn(documentService, 'getSuggestions')
    suggestionsSpy.mockReturnValue(of({ tags: [42, 43] }))
    initNormally()
    expect(suggestionsSpy).toHaveBeenCalled()
    expect(component.suggestions).toEqual({ tags: [42, 43] })
  })

  it('should show error if needed for get suggestions', () => {
    const suggestionsSpy = jest.spyOn(documentService, 'getSuggestions')
    const errorSpy = jest.spyOn(toastService, 'showError')
    suggestionsSpy.mockImplementationOnce(() =>
      throwError(() => new Error('failed to get suggestions'))
    )
    initNormally()
    expect(suggestionsSpy).toHaveBeenCalled()
    expect(errorSpy).toHaveBeenCalled()
  })

  it('should warn when open document does not match doc retrieved from backend on init', () => {
    let openModal: NgbModalRef
    modalService.activeInstances.subscribe((modals) => (openModal = modals[0]))
    const modalSpy = jest.spyOn(modalService, 'open')
    const openDoc = Object.assign({}, doc)
    // simulate a document being modified elsewhere and db updated
    doc.modified = new Date()
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: 3, section: 'details' })))
    jest.spyOn(documentService, 'get').mockReturnValueOnce(of(doc))
    jest.spyOn(openDocumentsService, 'getOpenDocument').mockReturnValue(openDoc)
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        count: customFields.length,
        all: customFields.map((f) => f.id),
        results: customFields,
      })
    )
    fixture.detectChanges() // calls ngOnInit
    expect(modalSpy).toHaveBeenCalledWith(ConfirmDialogComponent)
    const closeSpy = jest.spyOn(openModal, 'close')
    const confirmDialog = openModal.componentInstance as ConfirmDialogComponent
    confirmDialog.confirmClicked.next(confirmDialog)
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should change preview element by render type', () => {
    initNormally()
    component.document.archived_file_name = 'file.pdf'
    fixture.detectChanges()
    expect(component.archiveContentRenderType).toEqual(
      component.ContentRenderType.PDF
    )
    expect(
      fixture.debugElement.query(By.css('pdf-viewer-container'))
    ).not.toBeUndefined()

    component.document.archived_file_name = undefined
    component.document.mime_type = 'text/plain'
    fixture.detectChanges()
    expect(component.archiveContentRenderType).toEqual(
      component.ContentRenderType.Text
    )
    expect(
      fixture.debugElement.query(By.css('div.preview-sticky'))
    ).not.toBeUndefined()

    component.document.mime_type = 'image/jpeg'
    fixture.detectChanges()
    expect(component.archiveContentRenderType).toEqual(
      component.ContentRenderType.Image
    )
    expect(
      fixture.debugElement.query(By.css('.preview-sticky img'))
    ).not.toBeUndefined()
    ;(component.document.mime_type =
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
      fixture.detectChanges()
    expect(component.archiveContentRenderType).toEqual(
      component.ContentRenderType.Other
    )
    expect(
      fixture.debugElement.query(By.css('object.preview-sticky'))
    ).not.toBeUndefined()
  })

  it('should support split', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    initNormally()
    component.splitDocument()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.documentID = doc.id
    modal.componentInstance.totalPages = 5
    modal.componentInstance.page = 2
    modal.componentInstance.addSplit()
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    expect(req.request.body).toEqual({
      documents: [doc.id],
      method: 'split',
      parameters: { pages: '1-2,3-5', delete_originals: false },
    })
    req.error(new ProgressEvent('failed'))
    modal.componentInstance.confirm()
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
  })

  it('should support rotate', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    initNormally()
    component.rotateDocument()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.documentID = doc.id
    modal.componentInstance.rotate()
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    expect(req.request.body).toEqual({
      documents: [doc.id],
      method: 'rotate',
      parameters: { degrees: 90 },
    })
    req.error(new ProgressEvent('failed'))
    modal.componentInstance.confirm()
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
  })

  it('should support delete pages', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    initNormally()
    component.deletePages()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.documentID = doc.id
    modal.componentInstance.pages = [1, 2]
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    expect(req.request.body).toEqual({
      documents: [doc.id],
      method: 'delete_pages',
      parameters: { pages: [1, 2] },
    })
    req.error(new ProgressEvent('failed'))
    modal.componentInstance.confirm()
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
  })

  it('should support keyboard shortcuts', () => {
    initNormally()

    jest.spyOn(component, 'hasNext').mockReturnValue(true)
    const nextSpy = jest.spyOn(component, 'nextDoc')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'arrowright', ctrlKey: true })
    )
    expect(nextSpy).toHaveBeenCalled()

    jest.spyOn(component, 'hasPrevious').mockReturnValue(true)
    const prevSpy = jest.spyOn(component, 'previousDoc')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'arrowleft', ctrlKey: true })
    )
    expect(prevSpy).toHaveBeenCalled()

    jest.spyOn(openDocumentsService, 'isDirty').mockReturnValue(true)
    const saveSpy = jest.spyOn(component, 'save')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 's', ctrlKey: true })
    )
    expect(saveSpy).toHaveBeenCalled()

    jest.spyOn(openDocumentsService, 'isDirty').mockReturnValue(true)
    jest.spyOn(component, 'hasNext').mockReturnValue(true)
    const saveNextSpy = jest.spyOn(component, 'saveEditNext')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 's', ctrlKey: true, shiftKey: true })
    )
    expect(saveNextSpy).toHaveBeenCalled()

    const closeSpy = jest.spyOn(component, 'close')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'escape' }))
    expect(closeSpy).toHaveBeenCalled()
  })

  function initNormally() {
    jest
      .spyOn(activatedRoute, 'paramMap', 'get')
      .mockReturnValue(of(convertToParamMap({ id: 3, section: 'details' })))
    jest
      .spyOn(documentService, 'get')
      .mockReturnValueOnce(of(Object.assign({}, doc)))
    jest.spyOn(openDocumentsService, 'getOpenDocument').mockReturnValue(null)
    jest
      .spyOn(openDocumentsService, 'openDocument')
      .mockReturnValueOnce(of(true))
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        count: customFields.length,
        all: customFields.map((f) => f.id),
        results: customFields,
      })
    )
    fixture.detectChanges()
  }

  it('createDisabled should return true if the user does not have permission to add the specified data type', () => {
    currentUserCan = false
    expect(component.createDisabled(DataType.Correspondent)).toBeTruthy()
    expect(component.createDisabled(DataType.DocumentType)).toBeTruthy()
    expect(component.createDisabled(DataType.StoragePath)).toBeTruthy()
    expect(component.createDisabled(DataType.Tag)).toBeTruthy()
  })

  it('createDisabled should return false if the user has permission to add the specified data type', () => {
    currentUserCan = true
    expect(component.createDisabled(DataType.Correspondent)).toBeFalsy()
    expect(component.createDisabled(DataType.DocumentType)).toBeFalsy()
    expect(component.createDisabled(DataType.StoragePath)).toBeFalsy()
    expect(component.createDisabled(DataType.Tag)).toBeFalsy()
  })

  it('should call tryRenderTiff when no archive and file is tiff', () => {
    initNormally()
    const tiffRenderSpy = jest.spyOn(
      DocumentDetailComponent.prototype as any,
      'tryRenderTiff'
    )
    const doc = Object.assign({}, component.document)
    doc.archived_file_name = null
    doc.mime_type = 'image/tiff'
    jest
      .spyOn(documentService, 'getMetadata')
      .mockReturnValue(
        of({ has_archive_version: false, original_mime_type: 'image/tiff' })
      )
    component.updateComponent(doc)
    fixture.detectChanges()
    expect(component.archiveContentRenderType).toEqual(
      component.ContentRenderType.TIFF
    )
    expect(tiffRenderSpy).toHaveBeenCalled()
  })

  it('should try to render tiff and show error if failed', () => {
    initNormally()
    // just the text request
    httpTestingController.expectOne(component.previewUrl)

    // invalid tiff
    component['tryRenderTiff']()
    httpTestingController
      .expectOne(component.previewUrl)
      .flush(new ArrayBuffer(100)) // arraybuffer
    expect(component.tiffError).not.toBeUndefined()

    // http error
    component['tryRenderTiff']()
    httpTestingController
      .expectOne(component.previewUrl)
      .error(new ErrorEvent('failed'))
    expect(component.tiffError).not.toBeUndefined()
  })
})
