import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import {
  NgbModal,
  NgbPaginationModule,
  NgbModalRef,
  NgbModalModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { of, throwError } from 'rxjs'
import { Workflow } from 'src/app/data/workflow'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { WorkflowService } from 'src/app/services/rest/workflow.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { WorkflowsComponent } from './workflows.component'
import { WorkflowEditDialogComponent } from '../../common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component'
import { PermissionsService } from 'src/app/services/permissions.service'
import {
  DocumentSource,
  WorkflowTriggerType,
} from 'src/app/data/workflow-trigger'
import { WorkflowActionType } from 'src/app/data/workflow-action'

const workflows: Workflow[] = [
  {
    name: 'Workflow 1',
    id: 1,
    order: 1,
    enabled: true,
    triggers: [
      {
        id: 1,
        type: WorkflowTriggerType.Consumption,
        sources: [DocumentSource.ConsumeFolder],
        filter_filename: '*',
      },
    ],
    actions: [
      {
        id: 1,
        type: WorkflowActionType.Assignment,
        assign_title: 'foo',
      },
    ],
  },
  {
    name: 'Workflow 2',
    id: 2,
    order: 2,
    enabled: true,
    triggers: [
      {
        id: 2,
        type: WorkflowTriggerType.DocumentAdded,
        filter_filename: 'foo',
      },
    ],
    actions: [
      {
        id: 2,
        type: WorkflowActionType.Assignment,
        assign_title: 'bar',
      },
    ],
  },
]

describe('WorkflowsComponent', () => {
  let component: WorkflowsComponent
  let fixture: ComponentFixture<WorkflowsComponent>
  let workflowService: WorkflowService
  let modalService: NgbModal
  let toastService: ToastService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [
        WorkflowsComponent,
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
        NgbPopoverModule,
      ],
    })

    workflowService = TestBed.inject(WorkflowService)
    jest.spyOn(workflowService, 'listAll').mockReturnValue(
      of({
        count: workflows.length,
        all: workflows.map((o) => o.id),
        results: workflows,
      })
    )
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)

    fixture = TestBed.createComponent(WorkflowsComponent)
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
    const editDialog = modal.componentInstance as WorkflowEditDialogComponent

    // fail first
    editDialog.failed.emit({ error: 'error creating item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(workflows[0])
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
    const editDialog = modal.componentInstance as WorkflowEditDialogComponent
    expect(editDialog.object).toEqual(workflows[0])

    // fail first
    editDialog.failed.emit({ error: 'error editing item' })
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(workflows[0])
    expect(toastInfoSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support delete, show notification on error / success', () => {
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const deleteSpy = jest.spyOn(workflowService, 'delete')
    const reloadSpy = jest.spyOn(component, 'reload')

    const deleteButton = fixture.debugElement.queryAll(By.css('button'))[4]
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
