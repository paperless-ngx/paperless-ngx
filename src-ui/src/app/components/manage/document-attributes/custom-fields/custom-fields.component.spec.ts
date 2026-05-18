import { ComponentFixture, TestBed } from '@angular/core/testing'

import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbModal,
  NgbModalModule,
  NgbModalRef,
  NgbPaginationModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import {
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from 'src/app/data/custom-field-query'
import { FILTER_CUSTOM_FIELDS_QUERY } from 'src/app/data/filter-rule-type'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../../common/confirm-dialog/confirm-dialog.component'
import { CustomFieldEditDialogComponent } from '../../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { PageHeaderComponent } from '../../../common/page-header/page-header.component'
import { CustomFieldsComponent } from './custom-fields.component'

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
  let settingsService: SettingsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
        NgbPopoverModule,
        NgxBootstrapIconsModule.pick(allIcons),
        RouterTestingModule,
        CustomFieldsComponent,
        IfPermissionsDirective,
        PageHeaderComponent,
        ConfirmDialogComponent,
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
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 0, username: 'test' }

    fixture = TestBed.createComponent(CustomFieldsComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
    jest.useFakeTimers()
    jest.advanceTimersByTime(100)
  })

  it('should support create, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reload')

    component.editField()

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
    jest.advanceTimersByTime(100)
  })

  it('should support edit, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reload')

    const editButton = fixture.debugElement
      .queryAll(By.css('button'))
      .find((btn) =>
        btn.nativeElement.textContent.trim().includes(fields[0].name)
      )
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

    const deleteButton = fixture.debugElement
      .queryAll(By.css('button'))
      .find((btn) => btn.nativeElement.textContent.trim().includes('Delete'))
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

  it('should provide document filter url', () => {
    const urlSpy = jest.spyOn(listViewService, 'getQuickFilterUrl')
    component.getDocumentFilterUrl(fields[0])
    expect(urlSpy).toHaveBeenCalledWith([
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
