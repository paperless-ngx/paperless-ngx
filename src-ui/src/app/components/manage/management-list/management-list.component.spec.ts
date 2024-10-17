import { DatePipe } from '@angular/common'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbModal,
  NgbModalModule,
  NgbModalRef,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import { Tag } from 'src/app/data/tag'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { TagService } from 'src/app/services/rest/tag.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { TagListComponent } from '../tag-list/tag-list.component'
import { ManagementListComponent } from './management-list.component'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { ToastService } from 'src/app/services/toast.service'
import { EditDialogComponent } from '../../common/edit-dialog/edit-dialog.component'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { RouterTestingModule } from '@angular/router/testing'
import { routes } from 'src/app/app-routing.module'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { MATCH_AUTO } from 'src/app/data/matching-model'
import { MATCH_NONE } from 'src/app/data/matching-model'
import { MATCH_LITERAL } from 'src/app/data/matching-model'
import { PermissionsDialogComponent } from '../../common/permissions-dialog/permissions-dialog.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { BulkEditObjectOperation } from 'src/app/services/rest/abstract-name-filter-service'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

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

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        TagListComponent,
        SortableDirective,
        PageHeaderComponent,
        IfPermissionsDirective,
        SafeHtmlPipe,
        ConfirmDialogComponent,
        PermissionsDialogComponent,
      ],
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        RouterTestingModule.withRoutes(routes),
        NgxBootstrapIconsModule.pick(allIcons),
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
  }))

  it('should support create, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reloadData')

    const createButton = fixture.debugElement.queryAll(By.css('button'))[3]
    createButton.triggerEventHandler('click')

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

    const editButton = fixture.debugElement.queryAll(By.css('button'))[6]
    editButton.triggerEventHandler('click')

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

    const deleteButton = fixture.debugElement.queryAll(By.css('button'))[7]
    deleteButton.triggerEventHandler('click')

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

  it('should support quick filter for objects', () => {
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    const filterButton = fixture.debugElement.queryAll(By.css('button'))[8]
    filterButton.triggerEventHandler('click')
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_TAGS_ALL, value: tags[0].id.toString() },
    ]) // subclasses set the filter rule type
  })

  it('should reload on sort', () => {
    const reloadSpy = jest.spyOn(component, 'reloadData')
    const sortable = fixture.debugElement.query(By.directive(SortableDirective))
    sortable.triggerEventHandler('click')
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support toggle all items in view', () => {
    expect(component.selectedObjects.size).toEqual(0)
    const toggleAllSpy = jest.spyOn(component, 'toggleAll')
    const checkButton = fixture.debugElement.queryAll(
      By.css('input.form-check-input')
    )[0]
    checkButton.nativeElement.dispatchEvent(new Event('click'))
    checkButton.nativeElement.checked = true
    checkButton.nativeElement.dispatchEvent(new Event('click'))
    expect(toggleAllSpy).toHaveBeenCalled()
    expect(component.selectedObjects.size).toEqual(tags.length)
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
})
