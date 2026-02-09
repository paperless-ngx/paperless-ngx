import { DatePipe } from '@angular/common'
import {
  HttpErrorResponse,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { RouterLinkWithHref } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbModal,
  NgbModalModule,
  NgbModalRef,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import {
  MATCH_AUTO,
  MATCH_LITERAL,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import { Tag } from 'src/app/data/tag'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { BulkEditObjectOperation } from 'src/app/services/rest/abstract-name-filter-service'
import { TagService } from 'src/app/services/rest/tag.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogComponent } from '../../../common/edit-dialog/edit-dialog.component'
import { PageHeaderComponent } from '../../../common/page-header/page-header.component'
import { PermissionsDialogComponent } from '../../../common/permissions-dialog/permissions-dialog.component'
import { ManagementListComponent } from './management-list.component'
import { TagListComponent } from './tag-list/tag-list.component'

const tags: Tag[] = [
  {
    id: 1,
    name: 'Tag1 Foo',
    matching_algorithm: MATCH_LITERAL,
    match: 'foo',
    document_count: 35,
  },
  {
    id: 2,
    name: 'Tag2',
    matching_algorithm: MATCH_NONE,
    document_count: 0,
  },
  {
    id: 3,
    name: 'Tag3',
    matching_algorithm: MATCH_AUTO,
    document_count: 5,
  },
]

describe('ManagementListComponent', () => {
  let component: ManagementListComponent<Tag>
  let fixture: ComponentFixture<ManagementListComponent<Tag>>
  let tagService: TagService
  let modalService: NgbModal
  let toastService: ToastService
  let documentListViewService: DocumentListViewService
  let permissionsService: PermissionsService
  let settingsService: SettingsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        RouterTestingModule.withRoutes(routes),
        NgxBootstrapIconsModule.pick(allIcons),
        TagListComponent,
        SortableDirective,
        PageHeaderComponent,
        IfPermissionsDirective,
        ConfirmDialogComponent,
        PermissionsDialogComponent,
      ],
      providers: [
        DatePipe,
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    tagService = TestBed.inject(TagService)
    jest
      .spyOn(tagService, 'listFiltered')
      .mockImplementation(
        (page, pageSize, sortField, sortReverse, nameFilter, fullPerms) => {
          const results = nameFilter
            ? tags.filter((t) => t.name.toLowerCase().includes(nameFilter))
            : tags
          return of({
            count: results.length,
            all: results.map((o) => o.id),
            results,
          })
        }
      )
    permissionsService = TestBed.inject(PermissionsService)
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(true)
    jest
      .spyOn(permissionsService, 'currentUserOwnsObject')
      .mockReturnValue(true)
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)
    documentListViewService = TestBed.inject(DocumentListViewService)
    settingsService = TestBed.inject(SettingsService)
    fixture = TestBed.createComponent(TagListComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  // These tests are shared among all management list components

  it('should support filtering, clear on Esc key', fakeAsync(() => {
    const nameFilterInput = fixture.debugElement.query(By.css('input'))
    nameFilterInput.nativeElement.value = 'foo'
    // nameFilterInput.nativeElement.dispatchEvent(new Event('input'))
    component.nameFilter = 'foo' // subject normally triggered by ngModel
    tick(400) // debounce
    fixture.detectChanges()
    expect(component.data).toEqual([tags[0]])

    nameFilterInput.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { code: 'Escape' })
    )
    tick(400) // debounce
    fixture.detectChanges()
    expect(component.nameFilter).toBeNull()
    expect(component.data).toEqual(tags)
    tick(100) // load
  }))

  it('should support create, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reloadData')

    component.openCreateDialog()

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as EditDialogComponent<Tag>

    // fail first
    editDialog.failed.emit({ error: 'error creating item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit()
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support edit, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reloadData')

    component.openEditDialog(tags[0])

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as EditDialogComponent<Tag>
    expect(editDialog.object).toEqual(tags[0])

    // fail first
    editDialog.failed.emit({ error: 'error editing item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit()
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support delete, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const deleteSpy = jest.spyOn(tagService, 'delete')
    const reloadSpy = jest.spyOn(component, 'reloadData')

    component.openDeleteDialog(tags[0])

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as ConfirmDialogComponent

    // fail first
    deleteSpy.mockReturnValueOnce(throwError(() => new Error('error deleting')))
    editDialog.confirmClicked.emit()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    deleteSpy.mockReturnValueOnce(of(true))
    editDialog.confirmClicked.emit()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should use the all list length for collection size when provided', fakeAsync(() => {
    jest.spyOn(tagService, 'listFiltered').mockReturnValueOnce(
      of({
        count: 1,
        all: [1, 2, 3],
        results: tags.slice(0, 1),
      })
    )

    component.reloadData()
    tick(100)

    expect(component.collectionSize).toBe(3)
  }))

  it('should support quick filter for objects', () => {
    const expectedUrl = documentListViewService.getQuickFilterUrl([
      { rule_type: FILTER_HAS_TAGS_ALL, value: tags[0].id.toString() },
    ])
    const filterLink = fixture.debugElement.query(
      By.css('a.btn-outline-secondary')
    )
    expect(filterLink).toBeTruthy()
    const routerLink = filterLink.injector.get(RouterLinkWithHref)
    expect(routerLink.urlTree).toEqual(expectedUrl)
  })

  it('should reload on sort', () => {
    const reloadSpy = jest.spyOn(component, 'reloadData')
    const sortable = fixture.debugElement.query(By.directive(SortableDirective))
    sortable.triggerEventHandler('click')
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should fall back to first page if error is page is out of range', () => {
    jest.spyOn(tagService, 'listFiltered').mockReturnValueOnce(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 404,
            error: { detail: 'Invalid page' },
          })
      )
    )
    component.page = 2
    component.reloadData()
    expect(component.page).toEqual(1)
  })

  it('should support toggle select page in vew', () => {
    expect(component.selectedObjects.size).toEqual(0)
    const selectPageSpy = jest.spyOn(component, 'selectPage')
    const checkButton = fixture.debugElement.queryAll(
      By.css('input.form-check-input')
    )[0]
    checkButton.nativeElement.dispatchEvent(new Event('change'))
    checkButton.nativeElement.checked = true
    checkButton.nativeElement.dispatchEvent(new Event('change'))
    expect(selectPageSpy).toHaveBeenCalled()
    expect(component.selectedObjects.size).toEqual(tags.length)
  })

  it('selectNone should clear selection and reset toggle flag', () => {
    component.selectedObjects = new Set([tags[0].id, tags[1].id])
    component.togggleAll = true

    component.selectNone()

    expect(component.selectedObjects.size).toBe(0)
    expect(component.togggleAll).toBe(false)
  })

  it('selectPage should select current page items or clear selection', () => {
    component.selectPage()
    expect(component.selectedObjects).toEqual(new Set(tags.map((t) => t.id)))
    expect(component.togggleAll).toBe(true)

    component.togggleAll = true
    component.clearSelection()
    expect(component.selectedObjects.size).toBe(0)
    expect(component.togggleAll).toBe(false)
  })

  it('selectAll should use all IDs when collection size exists', () => {
    ;(component as any).allIDs = [1, 2, 3, 4]
    component.collectionSize = 4

    component.selectAll()

    expect(component.selectedObjects).toEqual(new Set([1, 2, 3, 4]))
    expect(component.togggleAll).toBe(true)
  })

  it('selectAll should clear selection when collection size is zero', () => {
    component.selectedObjects = new Set([1])
    component.collectionSize = 0
    component.togggleAll = true

    component.selectAll()

    expect(component.selectedObjects.size).toBe(0)
    expect(component.togggleAll).toBe(false)
  })

  it('toggleSelected should toggle object selection and update toggle state', () => {
    component.toggleSelected(tags[0])
    expect(component.selectedObjects.has(tags[0].id)).toBe(true)
    expect(component.togggleAll).toBe(false)

    component.toggleSelected(tags[1])
    component.toggleSelected(tags[2])
    expect(component.togggleAll).toBe(true)

    component.toggleSelected(tags[1])
    expect(component.selectedObjects.has(tags[1].id)).toBe(false)
    expect(component.togggleAll).toBe(false)
  })

  it('areAllPageItemsSelected should return false when page has no selectable items', () => {
    component.data = []
    component.selectedObjects.clear()

    expect((component as any).areAllPageItemsSelected()).toBe(false)

    component.data = tags
  })

  it('should support bulk edit permissions', () => {
    const bulkEditPermsSpy = jest.spyOn(tagService, 'bulk_edit_objects')
    component.toggleSelected(tags[0])
    component.toggleSelected(tags[1])
    component.toggleSelected(tags[2])
    component.toggleSelected(tags[2]) // uncheck, for coverage
    const selected = new Set([tags[0].id, tags[1].id])
    expect(component.selectedObjects).toEqual(selected)
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    fixture.detectChanges()
    component.setPermissions()
    expect(modal).not.toBeUndefined()

    // fail first
    bulkEditPermsSpy.mockReturnValueOnce(
      throwError(() => new Error('error setting permissions'))
    )
    const errorToastSpy = jest.spyOn(toastService, 'showError')
    modal.componentInstance.confirmClicked.emit({
      permissions: {},
      merge: true,
    })
    expect(bulkEditPermsSpy).toHaveBeenCalled()
    expect(errorToastSpy).toHaveBeenCalled()

    const successToastSpy = jest.spyOn(toastService, 'showInfo')
    bulkEditPermsSpy.mockReturnValueOnce(of('OK'))
    modal.componentInstance.confirmClicked.emit({
      permissions: {},
      merge: true,
    })
    expect(bulkEditPermsSpy).toHaveBeenCalled()
    expect(successToastSpy).toHaveBeenCalled()
  })

  it('should support bulk delete objects', () => {
    const bulkEditSpy = jest.spyOn(tagService, 'bulk_edit_objects')
    component.toggleSelected(tags[0])
    component.toggleSelected(tags[1])
    const selected = new Set([tags[0].id, tags[1].id])
    expect(component.selectedObjects).toEqual(selected)
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    fixture.detectChanges()
    component.delete()
    expect(modal).not.toBeUndefined()

    // fail first
    bulkEditSpy.mockReturnValueOnce(
      throwError(() => new Error('error setting permissions'))
    )
    const errorToastSpy = jest.spyOn(toastService, 'showError')
    modal.componentInstance.confirmClicked.emit(null)
    expect(bulkEditSpy).toHaveBeenCalledWith(
      Array.from(selected),
      BulkEditObjectOperation.Delete
    )
    expect(errorToastSpy).toHaveBeenCalled()

    const successToastSpy = jest.spyOn(toastService, 'showInfo')
    bulkEditSpy.mockReturnValueOnce(of('OK'))
    modal.componentInstance.confirmClicked.emit(null)
    expect(bulkEditSpy).toHaveBeenCalled()
    expect(successToastSpy).toHaveBeenCalled()
  })

  it('should disallow bulk permissions or delete objects if no global perms', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    expect(component.userCanBulkEdit(PermissionAction.Delete)).toBeFalsy()
    expect(component.userCanBulkEdit(PermissionAction.Change)).toBeFalsy()
  })

  it('should return an original object from filtered child object', () => {
    const childTag: Tag = {
      id: 4,
      name: 'Child Tag',
      matching_algorithm: MATCH_LITERAL,
      match: 'child',
      document_count: 10,
      parent: 1,
    }
    component['unfilteredData'].push(childTag)
    const original = component.getOriginalObject({ id: 4 } as Tag)
    expect(original).toEqual(childTag)
  })

  it('getSelectableIDs should return flat ids when not overridden', () => {
    const ids = (
      ManagementListComponent.prototype as any
    ).getSelectableIDs.call({}, [{ id: 1 }, { id: 5 }] as any)
    expect(ids).toEqual([1, 5])
  })

  it('pageSize getter should return stored page size or default to 25', () => {
    jest.spyOn(settingsService, 'get').mockReturnValue({ tags: 50 })
    component.typeNamePlural = 'tags'

    expect(component.pageSize).toBe(50)
  })

  it('pageSize getter should return 25 when no size is stored', () => {
    const settingsService = TestBed.inject(SettingsService)
    jest.spyOn(settingsService, 'get').mockReturnValue({})
    component.typeNamePlural = 'tags'

    expect(component.pageSize).toBe(25)
  })

  it('pageSize setter should update settings, reset page and reload data on success', fakeAsync(() => {
    const reloadSpy = jest.spyOn(component, 'reloadData')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')

    jest.spyOn(settingsService, 'get').mockReturnValue({ tags: 25 })
    jest.spyOn(settingsService, 'set').mockImplementation(() => {})
    jest
      .spyOn(settingsService, 'storeSettings')
      .mockReturnValue(of({ success: true }))

    component.typeNamePlural = 'tags'
    component.page = 2
    component.pageSize = 100

    tick()

    expect(settingsService.set).toHaveBeenCalledWith(
      SETTINGS_KEYS.OBJECT_LIST_SIZES,
      { tags: 100 }
    )
    expect(component.page).toBe(1)
    expect(reloadSpy).toHaveBeenCalled()
    expect(toastErrorSpy).not.toHaveBeenCalled()
  }))

  it('pageSize setter should show error toast on settings store failure', fakeAsync(() => {
    const reloadSpy = jest.spyOn(component, 'reloadData')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')

    jest.spyOn(settingsService, 'get').mockReturnValue({ tags: 25 })
    jest.spyOn(settingsService, 'set').mockImplementation(() => {})
    jest
      .spyOn(settingsService, 'storeSettings')
      .mockReturnValue(throwError(() => new Error('error storing settings')))

    component.typeNamePlural = 'tags'
    component.pageSize = 50

    tick()

    expect(toastErrorSpy).toHaveBeenCalledWith(
      'Error saving settings',
      expect.any(Error)
    )
    expect(reloadSpy).not.toHaveBeenCalled()
  }))
})
