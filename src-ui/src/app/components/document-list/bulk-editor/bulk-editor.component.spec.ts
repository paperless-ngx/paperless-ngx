import {
  HttpTestingController,
  HttpClientTestingModule,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbModal,
  NgbModule,
  NgbModalModule,
  NgbModalRef,
} from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import {
  SelectionData,
  DocumentService,
} from 'src/app/services/rest/document.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { FilterableDropdownComponent } from '../../common/filterable-dropdown/filterable-dropdown.component'
import { ToggleableDropdownButtonComponent } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import { PermissionsDialogComponent } from '../../common/permissions-dialog/permissions-dialog.component'
import { PermissionsFormComponent } from '../../common/input/permissions/permissions-form/permissions-form.component'
import { BulkEditorComponent } from './bulk-editor.component'
import { SelectComponent } from '../../common/input/select/select.component'
import { UserService } from 'src/app/services/rest/user.service'
import { PermissionsGroupComponent } from '../../common/input/permissions/permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../../common/input/permissions/permissions-user/permissions-user.component'
import { NgSelectModule } from '@ng-select/ng-select'
import { GroupService } from 'src/app/services/rest/group.service'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

const selectionData: SelectionData = {
  selected_tags: [
    { id: 12, document_count: 3 },
    { id: 22, document_count: 1 },
    { id: 19, document_count: 0 },
  ],
  selected_correspondents: [{ id: 33, document_count: 1 }],
  selected_document_types: [{ id: 44, document_count: 3 }],
  selected_storage_paths: [
    { id: 66, document_count: 3 },
    { id: 55, document_count: 0 },
  ],
}

describe('BulkEditorComponent', () => {
  let component: BulkEditorComponent
  let fixture: ComponentFixture<BulkEditorComponent>
  let permissionsService: PermissionsService
  let documentListViewService: DocumentListViewService
  let documentService: DocumentService
  let toastService: ToastService
  let modalService: NgbModal
  let httpTestingController: HttpTestingController

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        BulkEditorComponent,
        IfPermissionsDirective,
        FilterableDropdownComponent,
        ToggleableDropdownButtonComponent,
        FilterPipe,
        ConfirmDialogComponent,
        SafeHtmlPipe,
        PermissionsDialogComponent,
        PermissionsFormComponent,
        SelectComponent,
        PermissionsGroupComponent,
        PermissionsUserComponent,
      ],
      providers: [
        PermissionsService,
        {
          provide: TagService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  { id: 12, name: 'tag12' },
                  { id: 22, name: 'tag22' },
                ],
              }),
          },
        },
        {
          provide: CorrespondentService,
          useValue: {
            listAll: () =>
              of({
                results: [{ id: 33, name: 'correspondent33' }],
              }),
          },
        },
        {
          provide: DocumentTypeService,
          useValue: {
            listAll: () =>
              of({
                results: [{ id: 44, name: 'doctype44' }],
              }),
          },
        },
        {
          provide: StoragePathService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  { id: 66, name: 'storagepath66' },
                  { id: 55, name: 'storagepath55' },
                ],
              }),
          },
        },
        FilterPipe,
        SettingsService,
        {
          provide: UserService,
          useValue: {
            listAll: () =>
              of({
                results: [{ id: 1, username: 'user1' }],
              }),
          },
        },
        {
          provide: GroupService,
          useValue: {
            listAll: () =>
              of({
                results: [],
              }),
          },
        },
      ],
      imports: [
        HttpClientTestingModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModule,
        NgbModalModule,
        NgSelectModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    permissionsService = TestBed.inject(PermissionsService)
    documentListViewService = TestBed.inject(DocumentListViewService)
    documentService = TestBed.inject(DocumentService)
    toastService = TestBed.inject(ToastService)
    modalService = TestBed.inject(NgbModal)
    httpTestingController = TestBed.inject(HttpTestingController)

    fixture = TestBed.createComponent(BulkEditorComponent)
    component = fixture.componentInstance
  })

  afterEach(async () => {
    httpTestingController.verify()
  })

  it('should apply selection data to tags menu', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    fixture.detectChanges()
    expect(component.tagSelectionModel.getSelectedItems()).toHaveLength(0)
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 5, 7]))
    jest
      .spyOn(documentService, 'getSelectionData')
      .mockReturnValue(of(selectionData))
    component.openTagsDropdown()
    expect(component.tagSelectionModel.selectionSize()).toEqual(1)
  })

  it('should apply selection data to correspondents menu', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    fixture.detectChanges()
    expect(
      component.correspondentSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 5, 7]))
    jest
      .spyOn(documentService, 'getSelectionData')
      .mockReturnValue(of(selectionData))
    component.openCorrespondentDropdown()
    expect(component.correspondentSelectionModel.items).toHaveLength(2)
    expect(component.correspondentSelectionModel.selectionSize()).toEqual(0)
  })

  it('should apply selection data to doc types menu', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    fixture.detectChanges()
    expect(
      component.documentTypeSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 5, 7]))
    jest
      .spyOn(documentService, 'getSelectionData')
      .mockReturnValue(of(selectionData))
    component.openDocumentTypeDropdown()
    expect(component.documentTypeSelectionModel.selectionSize()).toEqual(1)
  })

  it('should apply selection data to storage path menu', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    fixture.detectChanges()
    expect(
      component.storagePathsSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 5, 7]))
    jest
      .spyOn(documentService, 'getSelectionData')
      .mockReturnValue(of(selectionData))
    component.openStoragePathDropdown()
    expect(component.storagePathsSelectionModel.selectionSize()).toEqual(1)
  })

  it('should execute modify tags bulk operation', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = false
    fixture.detectChanges()
    component.setTags({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'modify_tags',
      parameters: { add_tags: [101], remove_tags: [] },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should execute modify tags bulk operation with confirmation dialog if enabled', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setTags({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirm()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}documents/bulk_edit/`)
      .flush(true)
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should set modal dialog text accordingly for tag edit confirmation', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setTags({
      itemsToAdd: [],
      itemsToRemove: [{ id: 101, name: 'Tag 101' }],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will remove the tag "Tag 101" from 2 selected document(s).'
    )
    modal.close()
    component.setTags({
      itemsToAdd: [],
      itemsToRemove: [
        { id: 101, name: 'Tag 101' },
        { id: 102, name: 'Tag 102' },
      ],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will remove the tags "Tag 101" and "Tag 102" from 2 selected document(s).'
    )
    modal.close()
    component.setTags({
      itemsToAdd: [
        { id: 101, name: 'Tag 101' },
        { id: 102, name: 'Tag 102' },
      ],
      itemsToRemove: [],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will add the tags "Tag 101" and "Tag 102" to 2 selected document(s).'
    )
    modal.close()
    component.setTags({
      itemsToAdd: [
        { id: 101, name: 'Tag 101' },
        { id: 102, name: 'Tag 102' },
      ],
      itemsToRemove: [{ id: 103, name: 'Tag 103' }],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will add the tags "Tag 101" and "Tag 102" and remove the tags "Tag 103" on 2 selected document(s).'
    )
  })

  it('should execute modify correspondent bulk operation', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = false
    fixture.detectChanges()
    component.setCorrespondents({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'set_correspondent',
      parameters: { correspondent: 101 },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should execute modify correspondent bulk operation with confirmation dialog if enabled', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setCorrespondents({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirm()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}documents/bulk_edit/`)
      .flush(true)
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should set modal dialog text accordingly for correspondent edit confirmation', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setCorrespondents({
      itemsToAdd: [],
      itemsToRemove: [{ id: 101, name: 'Correspondent 101' }],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will remove the correspondent from 2 selected document(s).'
    )
    modal.close()
    component.setCorrespondents({
      itemsToAdd: [{ id: 101, name: 'Correspondent 101' }],
      itemsToRemove: [],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will assign the correspondent "Correspondent 101" to 2 selected document(s).'
    )
  })

  it('should execute modify document type bulk operation', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = false
    fixture.detectChanges()
    component.setDocumentTypes({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'set_document_type',
      parameters: { document_type: 101 },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should execute modify document type bulk operation with confirmation dialog if enabled', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setDocumentTypes({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirm()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}documents/bulk_edit/`)
      .flush(true)
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should set modal dialog text accordingly for document type edit confirmation', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setDocumentTypes({
      itemsToAdd: [],
      itemsToRemove: [{ id: 101, name: 'DocType 101' }],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will remove the document type from 2 selected document(s).'
    )
    modal.close()
    component.setDocumentTypes({
      itemsToAdd: [{ id: 101, name: 'DocType 101' }],
      itemsToRemove: [],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will assign the document type "DocType 101" to 2 selected document(s).'
    )
  })

  it('should execute modify storage path bulk operation', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = false
    fixture.detectChanges()
    component.setStoragePaths({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'set_storage_path',
      parameters: { storage_path: 101 },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should execute modify storage path bulk operation with confirmation dialog if enabled', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setStoragePaths({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirm()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}documents/bulk_edit/`)
      .flush(true)
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should set modal dialog text accordingly for storage path edit confirmation', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setStoragePaths({
      itemsToAdd: [],
      itemsToRemove: [{ id: 101, name: 'StoragePath 101' }],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will remove the storage path from 2 selected document(s).'
    )
    modal.close()
    component.setStoragePaths({
      itemsToAdd: [{ id: 101, name: 'StoragePath 101' }],
      itemsToRemove: [],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will assign the storage path "StoragePath 101" to 2 selected document(s).'
    )
  })

  it('should only execute bulk operations when changes are detected', () => {
    component.setTags({
      itemsToAdd: [],
      itemsToRemove: [],
    })
    component.setCorrespondents({
      itemsToAdd: [],
      itemsToRemove: [],
    })
    component.setDocumentTypes({
      itemsToAdd: [],
      itemsToRemove: [],
    })
    component.setStoragePaths({
      itemsToAdd: [],
      itemsToRemove: [],
    })
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
  })

  it('should support bulk delete with confirmation', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.applyDelete()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'delete',
      parameters: {},
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should not be accessible with insufficient global permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    fixture.detectChanges()
    const dropdown = fixture.debugElement.query(
      By.directive(FilterableDropdownComponent)
    )
    expect(dropdown).toBeNull()
  })

  it('should disable with insufficient object permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(false)
    fixture.detectChanges()
    const button = fixture.debugElement
      .query(By.directive(FilterableDropdownComponent))
      .query(By.css('button'))
    expect(button.nativeElement.disabled).toBeTruthy()
  })

  it('should show a warning toast on bulk edit error', () => {
    jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(
        throwError(() => new Error('error executing bulk operation'))
      )
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = false
    fixture.detectChanges()
    const toastSpy = jest.spyOn(toastService, 'showError')
    component.setTags({
      itemsToAdd: [{ id: 0 }],
      itemsToRemove: [],
    })
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should support redo ocr', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.redoOcrSelected()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'redo_ocr',
      parameters: {},
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should support bulk download with archive, originals or both and file formatting', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.downloadForm.get('downloadFileTypeArchive').patchValue(true)
    fixture.detectChanges()
    let downloadSpy = jest.spyOn(documentService, 'bulkDownload')
    //archive
    component.downloadSelected()
    expect(downloadSpy).toHaveBeenCalledWith([3, 4], 'archive', false)
    //originals
    component.downloadForm.get('downloadFileTypeArchive').patchValue(false)
    component.downloadForm.get('downloadFileTypeOriginals').patchValue(true)
    component.downloadSelected()
    expect(downloadSpy).toHaveBeenCalledWith([3, 4], 'originals', false)
    //both
    component.downloadForm.get('downloadFileTypeArchive').patchValue(true)
    component.downloadSelected()
    expect(downloadSpy).toHaveBeenCalledWith([3, 4], 'both', false)
    //formatting
    component.downloadForm.get('downloadUseFormatting').patchValue(true)
    component.downloadSelected()
    expect(downloadSpy).toHaveBeenCalledWith([3, 4], 'both', true)

    httpTestingController.match(
      `${environment.apiBaseUrl}documents/bulk_download/`
    )
  })

  it('should support bulk permissions update', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    component.showConfirmationDialogs = true
    fixture.detectChanges()
    component.setPermissions()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirmClicked.next()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'set_permissions',
      parameters: undefined,
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })
})
