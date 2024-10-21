import { ComponentFixture, TestBed } from '@angular/core/testing'

import { CustomFieldsComponent } from './custom-fields.component'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbModal,
  NgbPaginationModule,
  NgbModalModule,
  NgbModalRef,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_CUSTOM_FIELDS_QUERY } from 'src/app/data/filter-rule-type'
import {
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from 'src/app/data/custom-field-query'

const fields: CustomField[] = [
  {
    id: 0,
    name: 'Field 1',
    data_type: CustomFieldDataType.String,
  },
  {
    id: 1,
    name: 'Field 2',
    data_type: CustomFieldDataType.Integer,
  },
]

describe('CustomFieldsComponent', () => {
  let component: CustomFieldsComponent
  let fixture: ComponentFixture<CustomFieldsComponent>
  let customFieldsService: CustomFieldsService
  let modalService: NgbModal
  let toastService: ToastService
  let listViewService: DocumentListViewService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [
        CustomFieldsComponent,
        IfPermissionsDirective,
        PageHeaderComponent,
        ConfirmDialogComponent,
      ],
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        NgbPopoverModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
            currentUserHasObjectPermissions: () => true,
            currentUserOwnsObject: () => true,
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    customFieldsService = TestBed.inject(CustomFieldsService)
    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        count: fields.length,
        all: fields.map((o) => o.id),
        results: fields,
      })
    )
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)
    listViewService = TestBed.inject(DocumentListViewService)

    fixture = TestBed.createComponent(CustomFieldsComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support create, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reload')

    const createButton = fixture.debugElement.queryAll(By.css('button'))[1]
    createButton.triggerEventHandler('click')

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent

    // fail first
    editDialog.failed.emit({ error: 'error creating item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(fields[0])
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support edit, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reload')

    const editButton = fixture.debugElement.queryAll(By.css('button'))[2]
    editButton.triggerEventHandler('click')

    expect(modal).not.toBeUndefined()
    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent
    expect(editDialog.object).toEqual(fields[0])

    // fail first
    editDialog.failed.emit({ error: 'error editing item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(fields[0])
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support delete, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const deleteSpy = jest.spyOn(customFieldsService, 'delete')
    const reloadSpy = jest.spyOn(component, 'reload')

    const deleteButton = fixture.debugElement.queryAll(By.css('button'))[5]
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

  it('should support filter documents', () => {
    const filterSpy = jest.spyOn(listViewService, 'quickFilter')
    component.filterDocuments(fields[0])
    expect(filterSpy).toHaveBeenCalledWith([
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: JSON.stringify([
          CustomFieldQueryLogicalOperator.Or,
          [[fields[0].id, CustomFieldQueryOperator.Exists, true]],
        ]),
      },
    ])
  })
})
