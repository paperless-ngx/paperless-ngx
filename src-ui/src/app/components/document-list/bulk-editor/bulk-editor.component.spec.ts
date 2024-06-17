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
import { SwitchComponent } from '../../common/input/switch/switch.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { Results } from 'src/app/data/results'
import { Tag } from 'src/app/data/tag'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { StoragePath } from 'src/app/data/storage-path'
import { Warehouse } from 'src/app/data/warehouse'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { StoragePathEditDialogComponent } from '../../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { WarehouseEditDialogComponent } from '../../common/edit-dialog/warehouse-edit-dialog/warehouse-edit-dialog.component'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { RotateConfirmDialogComponent } from '../../common/confirm-dialog/rotate-confirm-dialog/rotate-confirm-dialog.component'
import { MergeConfirmDialogComponent } from '../../common/confirm-dialog/merge-confirm-dialog/merge-confirm-dialog.component'
import WarehouseService from 'src/app/services/rest/warehouse.service'

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
  selected_warehouses: []
}

describe('BulkEditorComponent', () => {
  let component: BulkEditorComponent
  let fixture: ComponentFixture<BulkEditorComponent>
  let permissionsService: PermissionsService
  let documentListViewService: DocumentListViewService
  let documentService: DocumentService
  let toastService: ToastService
  let modalService: NgbModal
  let tagService: TagService
  let correspondentsService: CorrespondentService
  let documentTypeService: DocumentTypeService
  let storagePathService: StoragePathService
  let warehouseService: WarehouseService
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
        SwitchComponent,
        RotateConfirmDialogComponent,
        IsNumberPipe,
        MergeConfirmDialogComponent,
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
        {
          provide: WarehouseService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  { id: 88, name: 'warehouse88' },
                  { id: 77, name: 'warehouse77' },
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
    tagService = TestBed.inject(TagService)
    correspondentsService = TestBed.inject(CorrespondentService)
    documentTypeService = TestBed.inject(DocumentTypeService)
    storagePathService = TestBed.inject(StoragePathService)
    warehouseService = TestBed.inject(WarehouseService)
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

  it('should apply selection data to warehouse menu', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    fixture.detectChanges()
    expect(
      component.warehousesSelectionModel.getSelectedItems()
    ).toHaveLength(0)
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 5, 7]))
    jest
      .spyOn(documentService, 'getSelectionData')
      .mockReturnValue(of(selectionData))
    component.openWarehouseDropdown()
    expect(component.warehousesSelectionModel.selectionSize()).toEqual(1)
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

  it('should execute modify warehouse bulk operation', () => {
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
    component.setWarehouses({
      itemsToAdd: [{ id: 101 }],
      itemsToRemove: [],
    })
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'set_warehouse',
      parameters: { warehouse: 101 },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should execute modify warehouse bulk operation with confirmation dialog if enabled', () => {
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
    component.setWarehouses({
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

  it('should set modal dialog text accordingly for warehouse edit confirmation', () => {
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
    component.setWarehouses({
      itemsToAdd: [],
      itemsToRemove: [{ id: 101, name: 'Warehouse 101' }],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will remove the warehouse from 2 selected document(s).'
    )
    modal.close()
    component.setWarehouses({
      itemsToAdd: [{ id: 101, name: 'Warehouse 101' }],
      itemsToRemove: [],
    })
    expect(modal.componentInstance.message).toEqual(
      'This operation will assign the storage path "Warehouse 101" to 2 selected document(s).'
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
    component.setWarehouses({
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

  it('should support rotate', () => {
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
    fixture.detectChanges()
    component.rotateSelected()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.rotate()
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'rotate',
      parameters: { degrees: 90 },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should support merge', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[0]))
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(documentListViewService, 'documents', 'get')
      .mockReturnValue([{ id: 3 }, { id: 4 }])
    jest
      .spyOn(documentService, 'getCachedMany')
      .mockReturnValue(of([{ id: 3 }, { id: 4 }]))
    jest
      .spyOn(documentListViewService, 'selected', 'get')
      .mockReturnValue(new Set([3, 4]))
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    fixture.detectChanges()
    component.mergeSelected()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.metadataDocumentID = 3
    modal.componentInstance.confirm()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'merge',
      parameters: { metadata_document_id: 3 },
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
    const perms = {
      permissions: {
        view_users: [],
        change_users: [],
        view_groups: [],
        change_groups: [],
      },
    }
    modal.componentInstance.confirmClicked.emit({
      permissions: perms,
      merge: true,
    })
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/bulk_edit/`
    )
    req.flush(true)
    expect(req.request.body).toEqual({
      documents: [3, 4],
      method: 'set_permissions',
      parameters: {
        permissions: perms.permissions,
        merge: true,
      },
    })
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=50&ordering=-created&truncate_content=true`
    ) // list reload
    httpTestingController.match(
      `${environment.apiBaseUrl}documents/?page=1&page_size=100000&fields=id`
    ) // listAllFilteredIds
  })

  it('should not attempt to retrieve objects if user does not have permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.tags).toBeUndefined()
    expect(component.correspondents).toBeUndefined()
    expect(component.documentTypes).toBeUndefined()
    expect(component.storagePaths).toBeUndefined()
    expect(component.warehouses).toBeUndefined()
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
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}documents/warehouses/`
    )
  })

  it('should support create new tag', () => {
    const name = 'New Tag'
    const newTag = { id: 101, name: 'New Tag' }
    const tags: Results<Tag> = {
      results: [
        { id: 1, name: 'Tag 1' },
        { id: 2, name: 'Tag 2' },
      ],
      count: 2,
      all: [1, 2],
    }

    const modalInstance = {
      componentInstance: {
        dialogMode: EditDialogMode.CREATE,
        object: { name },
        succeeded: of(newTag),
      },
    }
    const tagListAllSpy = jest.spyOn(tagService, 'listAll')
    tagListAllSpy.mockReturnValue(of(tags))

    const tagSelectionModelToggleSpy = jest.spyOn(
      component.tagSelectionModel,
      'toggle'
    )

    const modalServiceOpenSpy = jest.spyOn(modalService, 'open')
    modalServiceOpenSpy.mockReturnValue(modalInstance as any)

    component.createTag(name)

    expect(modalServiceOpenSpy).toHaveBeenCalledWith(TagEditDialogComponent, {
      backdrop: 'static',
    })
    expect(tagListAllSpy).toHaveBeenCalled()

    expect(tagSelectionModelToggleSpy).toHaveBeenCalledWith(newTag.id)
    expect(component.tags).toEqual(tags.results)
  })

  it('should support create new correspondent', () => {
    const name = 'New Correspondent'
    const newCorrespondent = { id: 101, name: 'New Correspondent' }
    const correspondents: Results<Correspondent> = {
      results: [
        { id: 1, name: 'Correspondent 1' },
        { id: 2, name: 'Correspondent 2' },
      ],
      count: 2,
      all: [1, 2],
    }

    const modalInstance = {
      componentInstance: {
        dialogMode: EditDialogMode.CREATE,
        object: { name },
        succeeded: of(newCorrespondent),
      },
    }
    const correspondentsListAllSpy = jest.spyOn(
      correspondentsService,
      'listAll'
    )
    correspondentsListAllSpy.mockReturnValue(of(correspondents))

    const correspondentSelectionModelToggleSpy = jest.spyOn(
      component.correspondentSelectionModel,
      'toggle'
    )

    const modalServiceOpenSpy = jest.spyOn(modalService, 'open')
    modalServiceOpenSpy.mockReturnValue(modalInstance as any)

    component.createCorrespondent(name)

    expect(modalServiceOpenSpy).toHaveBeenCalledWith(
      CorrespondentEditDialogComponent,
      { backdrop: 'static' }
    )
    expect(correspondentsListAllSpy).toHaveBeenCalled()

    expect(correspondentSelectionModelToggleSpy).toHaveBeenCalledWith(
      newCorrespondent.id
    )
    expect(component.correspondents).toEqual(correspondents.results)
  })

  it('should support create new document type', () => {
    const name = 'New Document Type'
    const newDocumentType = { id: 101, name: 'New Document Type' }
    const documentTypes: Results<DocumentType> = {
      results: [
        { id: 1, name: 'Document Type 1' },
        { id: 2, name: 'Document Type 2' },
      ],
      count: 2,
      all: [1, 2],
    }

    const modalInstance = {
      componentInstance: {
        dialogMode: EditDialogMode.CREATE,
        object: { name },
        succeeded: of(newDocumentType),
      },
    }
    const documentTypesListAllSpy = jest.spyOn(documentTypeService, 'listAll')
    documentTypesListAllSpy.mockReturnValue(of(documentTypes))

    const documentTypeSelectionModelToggleSpy = jest.spyOn(
      component.documentTypeSelectionModel,
      'toggle'
    )

    const modalServiceOpenSpy = jest.spyOn(modalService, 'open')
    modalServiceOpenSpy.mockReturnValue(modalInstance as any)

    component.createDocumentType(name)

    expect(modalServiceOpenSpy).toHaveBeenCalledWith(
      DocumentTypeEditDialogComponent,
      { backdrop: 'static' }
    )
    expect(documentTypesListAllSpy).toHaveBeenCalled()

    expect(documentTypeSelectionModelToggleSpy).toHaveBeenCalledWith(
      newDocumentType.id
    )
    expect(component.documentTypes).toEqual(documentTypes.results)
  })

  it('should support create new storage path', () => {
    const name = 'New Storage Path'
    const newStoragePath = { id: 101, name: 'New Storage Path' }
    const storagePaths: Results<StoragePath> = {
      results: [
        { id: 1, name: 'Storage Path 1' },
        { id: 2, name: 'Storage Path 2' },
      ],
      count: 2,
      all: [1, 2],
    }

    const modalInstance = {
      componentInstance: {
        dialogMode: EditDialogMode.CREATE,
        object: { name },
        succeeded: of(newStoragePath),
      },
    }
    const storagePathsListAllSpy = jest.spyOn(storagePathService, 'listAll')
    storagePathsListAllSpy.mockReturnValue(of(storagePaths))

    const storagePathsSelectionModelToggleSpy = jest.spyOn(
      component.storagePathsSelectionModel,
      'toggle'
    )

    const modalServiceOpenSpy = jest.spyOn(modalService, 'open')
    modalServiceOpenSpy.mockReturnValue(modalInstance as any)

    component.createStoragePath(name)

    expect(modalServiceOpenSpy).toHaveBeenCalledWith(
      StoragePathEditDialogComponent,
      { backdrop: 'static' }
    )
    expect(storagePathsListAllSpy).toHaveBeenCalled()

    expect(storagePathsSelectionModelToggleSpy).toHaveBeenCalledWith(
      newStoragePath.id
    )
    expect(component.storagePaths).toEqual(storagePaths.results)
  })

  it('should support create new warehouse', () => {
    const name = 'New Warehouse'
    const newWarehouse = { id: 101, name: 'New Warehouse' }
    const warehouses: Results<Warehouse> = {
      results: [
        { id: 1, name: 'Warehouse 1' },
        { id: 2, name: 'Warehouse 2' },
      ],
      count: 2,
      all: [1, 2],
    }

    const modalInstance = {
      componentInstance: {
        dialogMode: EditDialogMode.CREATE,
        object: { name },
        succeeded: of(newWarehouse),
      },
    }
    const warehousesListAllSpy = jest.spyOn(warehouseService, 'listAll')
    warehousesListAllSpy.mockReturnValue(of(warehouses))

    const warehousesSelectionModelToggleSpy = jest.spyOn(
      component.warehousesSelectionModel,
      'toggle'
    )

    const modalServiceOpenSpy = jest.spyOn(modalService, 'open')
    modalServiceOpenSpy.mockReturnValue(modalInstance as any)

    component.createWarehouse(name)

    expect(modalServiceOpenSpy).toHaveBeenCalledWith(
      WarehouseEditDialogComponent,
      { backdrop: 'static' }
    )
    expect(warehousesListAllSpy).toHaveBeenCalled()

    expect(warehousesSelectionModelToggleSpy).toHaveBeenCalledWith(
      newWarehouse.id
    )
    expect(component.warehouses).toEqual(warehouses.results)
  })
})
