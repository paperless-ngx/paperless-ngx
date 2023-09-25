import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbModal,
  NgbPaginationModule,
  NgbModalRef,
  NgbModalModule,
} from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import {
  DocumentSource,
  PaperlessConsumptionTemplate,
} from 'src/app/data/paperless-consumption-template'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { ConsumptionTemplateService } from 'src/app/services/rest/consumption-template.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { ConsumptionTemplatesComponent } from './consumption-templates.component'
import { ConsumptionTemplateEditDialogComponent } from '../../common/edit-dialog/consumption-template-edit-dialog/consumption-template-edit-dialog.component'
import { PermissionsService } from 'src/app/services/permissions.service'

const templates: PaperlessConsumptionTemplate[] = [
  {
    id: 0,
    name: 'Template 1',
    order: 0,
    sources: [
      DocumentSource.ConsumeFolder,
      DocumentSource.ApiUpload,
      DocumentSource.MailFetch,
    ],
    filter_filename: 'foo',
    filter_path: 'bar',
    assign_tags: [1, 2, 3],
  },
  {
    id: 1,
    name: 'Template 2',
    order: 1,
    sources: [DocumentSource.MailFetch],
    filter_filename: null,
    filter_path: 'foo/bar',
    assign_owner: 1,
  },
]

describe('ConsumptionTemplatesComponent', () => {
  let component: ConsumptionTemplatesComponent
  let fixture: ComponentFixture<ConsumptionTemplatesComponent>
  let consumptionTemplateService: ConsumptionTemplateService
  let modalService: NgbModal
  let toastService: ToastService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [
        ConsumptionTemplatesComponent,
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
      ],
      imports: [
        HttpClientTestingModule,
        NgbPaginationModule,
        FormsModule,
        ReactiveFormsModule,
        NgbModalModule,
      ],
    })

    consumptionTemplateService = TestBed.inject(ConsumptionTemplateService)
    jest.spyOn(consumptionTemplateService, 'listAll').mockReturnValue(
      of({
        count: templates.length,
        all: templates.map((o) => o.id),
        results: templates,
      })
    )
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)

    fixture = TestBed.createComponent(ConsumptionTemplatesComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support create, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reload')

    const createButton = fixture.debugElement.queryAll(By.css('button'))[0]
    createButton.triggerEventHandler('click')

    expect(modal).not.toBeUndefined()
    const editDialog =
      modal.componentInstance as ConsumptionTemplateEditDialogComponent

    // fail first
    editDialog.failed.emit({ error: 'error creating item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(templates[0])
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support edit, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')
    const reloadSpy = jest.spyOn(component, 'reload')

    const editButton = fixture.debugElement.queryAll(By.css('button'))[1]
    editButton.triggerEventHandler('click')

    expect(modal).not.toBeUndefined()
    const editDialog =
      modal.componentInstance as ConsumptionTemplateEditDialogComponent
    expect(editDialog.object).toEqual(templates[0])

    // fail first
    editDialog.failed.emit({ error: 'error editing item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(templates[0])
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support delete, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const deleteSpy = jest.spyOn(consumptionTemplateService, 'delete')
    const reloadSpy = jest.spyOn(component, 'reload')

    const deleteButton = fixture.debugElement.queryAll(By.css('button'))[3]
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
})
