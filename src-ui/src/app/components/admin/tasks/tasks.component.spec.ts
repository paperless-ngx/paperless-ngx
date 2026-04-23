import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { Router } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { NgbModal, NgbModalRef, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { throwError } from 'rxjs'
import { routes } from 'src/app/app-routing.module'
import {
  PaperlessTask,
  PaperlessTaskStatus,
  PaperlessTaskTriggerSource,
  PaperlessTaskType,
} from 'src/app/data/paperless-task'
import { Results } from 'src/app/data/results'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { TasksService } from 'src/app/services/tasks.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { TasksComponent, TaskSection } from './tasks.component'

const tasks: PaperlessTask[] = [
  {
    id: 467,
    task_id: '11ca1a5b-9f81-442c-b2c8-7e4ae53657f1',
    input_data: { filename: 'test.pdf' },
    date_created: new Date('2023-03-01T10:26:03.093116Z'),
    date_done: new Date('2023-03-01T10:26:07.223048Z'),
    task_type: PaperlessTaskType.ConsumeFile,
    task_type_display: 'Consume File',
    trigger_source: PaperlessTaskTriggerSource.FolderConsume,
    trigger_source_display: 'Folder Consume',
    status: PaperlessTaskStatus.Failure,
    status_display: 'Failure',
    result_data: {
      error_message:
        'test.pd: Not consuming test.pdf: It is a duplicate of test (#100)',
    },
    acknowledged: false,
    related_document_ids: [],
  },
  {
    id: 466,
    task_id: '10ca1a5b-3c08-442c-b2c8-7e4ae53657f1',
    input_data: { filename: '191092.pdf' },
    date_created: new Date('2023-03-01T09:26:03.093116Z'),
    date_done: new Date('2023-03-01T09:26:07.223048Z'),
    task_type: PaperlessTaskType.ConsumeFile,
    task_type_display: 'Consume File',
    trigger_source: PaperlessTaskTriggerSource.FolderConsume,
    trigger_source_display: 'Folder Consume',
    status: PaperlessTaskStatus.Failure,
    status_display: 'Failure',
    result_data: { duplicate_of: 311 },
    acknowledged: false,
    related_document_ids: [],
  },
  {
    id: 465,
    task_id: '3612d477-bb04-44e3-985b-ac580dd496d8',
    input_data: { filename: 'Scan Jun 6, 2023 at 3.19 PM.pdf' },
    date_created: new Date('2023-06-06T15:22:05.722323-07:00'),
    date_done: new Date('2023-06-06T15:22:14.564305-07:00'),
    task_type: PaperlessTaskType.ConsumeFile,
    task_type_display: 'Consume File',
    trigger_source: PaperlessTaskTriggerSource.FolderConsume,
    trigger_source_display: 'Folder Consume',
    status: PaperlessTaskStatus.Pending,
    status_display: 'Pending',
    result_data: null,
    acknowledged: false,
    related_document_ids: [],
  },
  {
    id: 464,
    task_id: '2eac4716-2aa6-4dcd-9953-264e11656d7e',
    input_data: { filename: 'paperless-mail-l4dkg8ir' },
    date_created: new Date('2023-06-04T11:24:32.898089-07:00'),
    date_done: new Date('2023-06-04T11:24:44.678605-07:00'),
    task_type: PaperlessTaskType.ConsumeFile,
    task_type_display: 'Consume File',
    trigger_source: PaperlessTaskTriggerSource.EmailConsume,
    trigger_source_display: 'Email Consume',
    status: PaperlessTaskStatus.Success,
    status_display: 'Success',
    result_data: { document_id: 422, duplicate_of: 99 },
    acknowledged: false,
    related_document_ids: [422],
  },
  {
    id: 463,
    task_id: '28125528-1575-4d6b-99e6-168906e8fa5c',
    input_data: { filename: 'onlinePaymentSummary.pdf' },
    date_created: new Date('2023-06-01T13:49:51.631305-07:00'),
    date_done: new Date('2023-06-01T13:49:54.190220-07:00'),
    task_type: PaperlessTaskType.ConsumeFile,
    task_type_display: 'Consume File',
    trigger_source: PaperlessTaskTriggerSource.FolderConsume,
    trigger_source_display: 'Folder Consume',
    status: PaperlessTaskStatus.Success,
    status_display: 'Success',
    result_data: { document_id: 421 },
    acknowledged: false,
    related_document_ids: [421],
  },
  {
    id: 462,
    task_id: 'a5b9ca47-0c8e-490f-a04c-6db5d5fc09e5',
    input_data: { filename: 'paperless-mail-_rrpmqk6' },
    date_created: new Date('2023-06-07T02:54:35.694916Z'),
    date_done: null,
    task_type: PaperlessTaskType.ConsumeFile,
    task_type_display: 'Consume File',
    trigger_source: PaperlessTaskTriggerSource.EmailConsume,
    trigger_source_display: 'Email Consume',
    status: PaperlessTaskStatus.Started,
    status_display: 'Started',
    result_data: null,
    acknowledged: false,
    related_document_ids: [],
  },
  {
    id: 461,
    task_id: 'bb79efb3-1e78-4f31-b4be-0966620b0ce1',
    input_data: { dry_run: false, scope: 'global' },
    date_created: new Date('2023-06-07T03:54:35.694916Z'),
    date_done: null,
    task_type: PaperlessTaskType.SanityCheck,
    task_type_display: 'Sanity Check',
    trigger_source: PaperlessTaskTriggerSource.System,
    trigger_source_display: 'System',
    status: PaperlessTaskStatus.Started,
    status_display: 'Started',
    result_data: { issues_found: 0 },
    acknowledged: false,
    related_document_ids: [],
  },
]

const paginatedTasks: Results<PaperlessTask> = {
  count: tasks.length,
  results: tasks,
}

describe('TasksComponent', () => {
  let component: TasksComponent
  let fixture: ComponentFixture<TasksComponent>
  let tasksService: TasksService
  let modalService: NgbModal
  let router: Router
  let httpTestingController: HttpTestingController
  let reloadSpy
  let toastService: ToastService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        RouterTestingModule.withRoutes(routes),
        NgxBootstrapIconsModule.pick(allIcons),
        FormsModule,
        TasksComponent,
        PageHeaderComponent,
        IfPermissionsDirective,
        CustomDatePipe,
        ConfirmDialogComponent,
      ],
      providers: [
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        CustomDatePipe,
        DatePipe,
        PermissionsGuard,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    tasksService = TestBed.inject(TasksService)
    reloadSpy = jest.spyOn(tasksService, 'reload')
    httpTestingController = TestBed.inject(HttpTestingController)
    modalService = TestBed.inject(NgbModal)
    router = TestBed.inject(Router)
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(TasksComponent)
    component = fixture.componentInstance
    jest.useFakeTimers()
    fixture.detectChanges()

    httpTestingController
      .expectOne(
        (req) =>
          req.url === `${environment.apiBaseUrl}tasks/` &&
          req.params.get('acknowledged') === 'false' &&
          req.params.get('page_size') === '1000'
      )
      .flush(paginatedTasks)

    httpTestingController
      .expectOne(
        (req) =>
          req.url === `${environment.apiBaseUrl}tasks/` &&
          req.params.get('acknowledged') === 'false' &&
          req.params.get('page_size') === '25' &&
          req.params.get('page') === '1'
      )
      .flush(paginatedTasks)
  })

  it('should display task sections with counts', () => {
    expect(component.selectedSection).toBe(TaskSection.All)
    expect(component.selectedTaskType).toBeNull()
    expect(component.selectedTriggerSource).toBeNull()

    fixture.detectChanges()

    const viewScope = fixture.debugElement.query(By.css('.task-view-scope'))
    const text = viewScope.nativeElement.textContent

    expect(text).toContain('All')
    expect(text).toContain('Needs attention')
    expect(text).toContain('2')
    expect(text).toContain('In progress')
    expect(text).toContain('3')
    expect(text).toContain('Recently completed')
  })

  it('should filter visible sections by selected status', () => {
    component.setSection(TaskSection.InProgress)
    fixture.detectChanges()

    expect(component.visibleSections).toEqual([TaskSection.InProgress])
    expect(fixture.nativeElement.textContent).toContain('In progress')
    expect(fixture.nativeElement.textContent).not.toContain('Recent completed')
  })

  it('should filter tasks by task type', () => {
    component.setSection(TaskSection.InProgress)
    component.setTaskType(PaperlessTaskType.SanityCheck)

    expect(component.tasksForSection(TaskSection.InProgress)).toHaveLength(1)
    expect(component.tasksForSection(TaskSection.InProgress)[0].task_type).toBe(
      PaperlessTaskType.SanityCheck
    )
  })

  it('should filter tasks by trigger source', () => {
    component.setSection(TaskSection.InProgress)
    component.setTriggerSource(PaperlessTaskTriggerSource.EmailConsume)

    expect(component.tasksForSection(TaskSection.InProgress)).toHaveLength(1)
    expect(
      component.tasksForSection(TaskSection.InProgress)[0].trigger_source
    ).toBe(PaperlessTaskTriggerSource.EmailConsume)
  })

  it('should reset all active filters together', () => {
    component.setSection(TaskSection.InProgress)
    component.setTaskType(PaperlessTaskType.SanityCheck)
    component.setTriggerSource(PaperlessTaskTriggerSource.System)
    component.filterText = 'system'
    jest.advanceTimersByTime(150)

    expect(component.isFiltered).toBe(true)

    component.resetFilters()

    expect(component.selectedSection).toBe(TaskSection.InProgress)
    expect(component.selectedTaskType).toBeNull()
    expect(component.selectedTriggerSource).toBeNull()
    expect(component.filterText).toBe('')
    expect(component.isFiltered).toBe(false)
  })

  it('should keep header controls focused on actions and auto refresh', () => {
    fixture.detectChanges()

    const header = fixture.debugElement.query(By.css('pngx-page-header'))
    const headerText = header.nativeElement.textContent

    expect(headerText).toContain('Dismiss visible')
    expect(headerText).toContain('Auto refresh')
    expect(headerText).not.toContain('All types')
    expect(headerText).not.toContain('All sources')
    expect(headerText).not.toContain('Reset filters')
  })

  it('should render the view scope row above the filter bar', () => {
    fixture.detectChanges()

    const controls = fixture.debugElement.query(By.css('.task-controls'))
    const viewScope = controls.query(By.css('.task-view-scope'))
    const search = controls.query(By.css('.task-search'))

    expect(viewScope).not.toBeNull()
    expect(search).not.toBeNull()
    expect(
      viewScope.nativeElement.compareDocumentPosition(search.nativeElement) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it('should render pagination controls next to the task filter', () => {
    fixture.detectChanges()

    const controls = fixture.debugElement.query(By.css('.task-controls'))
    const search = controls.query(By.css('.task-search'))
    const pagination = controls.query(By.css('ngb-pagination'))

    expect(search).not.toBeNull()
    expect(pagination).not.toBeNull()
  })

  it('should load a different task page when pagination changes', () => {
    component.setPage(2)

    const pageTwoTasks = {
      count: 30,
      results: [tasks[0]],
    }

    httpTestingController
      .expectOne(
        (req) =>
          req.url === `${environment.apiBaseUrl}tasks/` &&
          req.params.get('acknowledged') === 'false' &&
          req.params.get('page_size') === '25' &&
          req.params.get('page') === '2'
      )
      .flush(pageTwoTasks)

    expect(component.page).toBe(2)
    expect(component.totalTasks).toBe(30)
    expect(component.pagedTasks).toEqual([tasks[0]])
  })

  it('should expose stable task type options and disable empty ones', () => {
    expect(component.taskTypeOptions.map((option) => option.value)).toContain(
      PaperlessTaskType.TrainClassifier
    )
    expect(
      component.isTaskTypeOptionDisabled(PaperlessTaskType.TrainClassifier)
    ).toBe(true)
    expect(
      component.isTaskTypeOptionDisabled(PaperlessTaskType.ConsumeFile)
    ).toBe(false)
  })

  it('should fall back to the raw selected task type label when no option matches', () => {
    component.selectedTaskType = 'unknown_task_type' as PaperlessTaskType

    expect(component.selectedTaskTypeLabel).toBe('unknown_task_type')
  })

  it('should expose stable trigger source options and disable empty ones', () => {
    expect(
      component.triggerSourceOptions.map((option) => option.value)
    ).toContain(PaperlessTaskTriggerSource.ApiUpload)
    expect(
      component.isTriggerSourceOptionDisabled(
        PaperlessTaskTriggerSource.ApiUpload
      )
    ).toBe(true)
    expect(
      component.isTriggerSourceOptionDisabled(
        PaperlessTaskTriggerSource.EmailConsume
      )
    ).toBe(false)
  })

  it('should fall back to the raw selected trigger source label when no option matches', () => {
    component.selectedTriggerSource =
      'unknown_trigger_source' as PaperlessTaskTriggerSource

    expect(component.selectedTriggerSourceLabel).toBe('unknown_trigger_source')
  })

  it('should support expanding / collapsing one task at a time', () => {
    component.expandTask(tasks[0])
    expect(component.expandedTask).toEqual(tasks[0].id)
    component.expandTask(tasks[1])
    expect(component.expandedTask).toEqual(tasks[1].id)
    component.expandTask(tasks[1])
    expect(component.expandedTask).toBeUndefined()
  })

  it('should show structured task details when expanded', () => {
    component.setSection(TaskSection.InProgress)
    component.expandTask(tasks[6])
    fixture.detectChanges()

    const detailText = fixture.nativeElement.textContent

    expect(detailText).toContain('Input data')
    expect(detailText).toContain('Result data')
    expect(detailText).toContain('"scope": "global"')
    expect(detailText).toContain('"issues_found": 0')
  })

  it('should show duplicate warnings and duplicate details when present', () => {
    component.setSection(TaskSection.Completed)
    component.expandTask(tasks[3])
    fixture.detectChanges()

    const content = fixture.nativeElement.textContent

    expect(content).toContain('Duplicate of document #99')
    expect(content).toContain('Duplicate')
    expect(content).toContain('Open')
  })

  it('should support dismiss single task', () => {
    const dismissSpy = jest.spyOn(tasksService, 'dismissTasks')
    component.dismissTask(tasks[0])
    expect(dismissSpy).toHaveBeenCalledWith(new Set([tasks[0].id]))
  })

  it('should support dismiss specific checked tasks', () => {
    component.toggleSelected(tasks[0])
    component.toggleSelected(tasks[1])
    component.toggleSelected(tasks[3])
    component.toggleSelected(tasks[3])
    const selected = new Set([tasks[0].id, tasks[1].id])
    expect(component.selectedTasks).toEqual(selected)
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const dismissSpy = jest.spyOn(tasksService, 'dismissTasks')
    fixture.detectChanges()
    component.dismissTasks()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirmClicked.emit()
    expect(dismissSpy).toHaveBeenCalledWith(selected)
  })

  it('should show an error and re-enable modal buttons when dismissing multiple tasks fails', () => {
    component.selectedTasks = new Set([tasks[0].id, tasks[1].id])
    const error = new Error('dismiss failed')
    const toastSpy = jest.spyOn(toastService, 'showError')
    const dismissSpy = jest
      .spyOn(tasksService, 'dismissTasks')
      .mockReturnValue(throwError(() => error))

    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))

    component.dismissTasks()
    expect(modal).not.toBeUndefined()

    modal.componentInstance.confirmClicked.emit()

    expect(dismissSpy).toHaveBeenCalledWith(new Set([tasks[0].id, tasks[1].id]))
    expect(toastSpy).toHaveBeenCalledWith('Error dismissing tasks', error)
    expect(modal.componentInstance.buttonsEnabled).toBe(true)
    expect(component.selectedTasks.size).toBe(0)
  })

  it('should show an error when dismissing a single task fails', () => {
    const error = new Error('dismiss failed')
    const toastSpy = jest.spyOn(toastService, 'showError')
    const dismissSpy = jest
      .spyOn(tasksService, 'dismissTasks')
      .mockReturnValue(throwError(() => error))

    component.dismissTask(tasks[0])

    expect(dismissSpy).toHaveBeenCalledWith(new Set([tasks[0].id]))
    expect(toastSpy).toHaveBeenCalledWith('Error dismissing task', error)
    expect(component.selectedTasks.size).toBe(0)
  })

  it('should support dismiss visible tasks', () => {
    component.setSection(TaskSection.NeedsAttention)
    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))
    const dismissSpy = jest.spyOn(tasksService, 'dismissTasks')
    component.dismissTasks()
    expect(modal).not.toBeUndefined()
    modal.componentInstance.confirmClicked.emit()
    expect(dismissSpy).toHaveBeenCalledWith(new Set([467, 466]))
  })

  it('should dismiss the currently visible scoped and filtered tasks', () => {
    component.setSection(TaskSection.InProgress)
    component.setTaskType(PaperlessTaskType.SanityCheck)
    component.setTriggerSource(PaperlessTaskTriggerSource.System)

    const dismissSpy = jest.spyOn(tasksService, 'dismissTasks')

    component.dismissTasks()

    expect(dismissSpy).toHaveBeenCalledWith(new Set([461]))
  })

  it('should support toggling a full section', () => {
    component.setSection(TaskSection.NeedsAttention)
    fixture.detectChanges()

    const toggleCheck = fixture.debugElement.query(
      By.css('#all-tasks-needs_attention')
    )
    expect(toggleCheck).not.toBeNull()
    toggleCheck.nativeElement.dispatchEvent(new MouseEvent('click'))
    fixture.detectChanges()
    expect(component.selectedTasks).toEqual(new Set([467, 466]))
  })

  it('should remove a full section from selection when toggled off', () => {
    component.setSection(TaskSection.NeedsAttention)
    component.selectedTasks = new Set([467, 466])

    component.toggleSection(TaskSection.NeedsAttention, {
      target: { checked: false },
    } as unknown as PointerEvent)

    expect(component.selectedTasks).toEqual(new Set())
  })

  it('should support dismiss and open a document', () => {
    const routerSpy = jest.spyOn(router, 'navigate')
    component.dismissAndGo(tasks[3])
    expect(routerSpy).toHaveBeenCalledWith([
      'documents',
      tasks[3].related_document_ids?.[0],
    ])
  })

  it('should auto refresh, allow toggle', () => {
    expect(reloadSpy).toHaveBeenCalledTimes(1)
    jest.advanceTimersByTime(5000)
    expect(reloadSpy).toHaveBeenCalledTimes(2)
    component.autoRefreshEnabled = false
    jest.advanceTimersByTime(6000)
    expect(reloadSpy).toHaveBeenCalledTimes(2)
  })

  it('should filter tasks by file name', () => {
    fixture.detectChanges()
    const input = fixture.debugElement.query(
      By.css('.task-search input[type=text]')
    )
    expect(input).not.toBeNull()
    input.nativeElement.value = '191092'
    input.nativeElement.dispatchEvent(new Event('input'))
    jest.advanceTimersByTime(150)
    fixture.detectChanges()
    expect(component.filterText).toEqual('191092')
    expect(component.tasksForSection(TaskSection.NeedsAttention)).toHaveLength(
      1
    )
  })

  it('should match task type and source in name filtering', () => {
    component.setSection(TaskSection.InProgress)
    component.filterText = 'system'
    jest.advanceTimersByTime(150)

    expect(component.tasksForSection(TaskSection.InProgress)).toHaveLength(1)
    expect(component.tasksForSection(TaskSection.InProgress)[0].task_type).toBe(
      PaperlessTaskType.SanityCheck
    )
  })

  it('should fall back to task type when filename is unavailable', () => {
    component.setSection(TaskSection.InProgress)
    fixture.detectChanges()

    const nameColumn = fixture.debugElement.queryAll(
      By.css('tbody td.name-col')
    )
    const sanityTaskRow = nameColumn.find((cell) =>
      cell.nativeElement.textContent.includes('Sanity Check')
    )

    expect(sanityTaskRow.nativeElement.textContent).toContain('Sanity Check')
    expect(sanityTaskRow.nativeElement.textContent).toContain('System')
  })

  it('should filter tasks by result', () => {
    component.setSection(TaskSection.NeedsAttention)
    component.filterTargetID = 1
    fixture.detectChanges()
    const input = fixture.debugElement.query(
      By.css('.task-search input[type=text]')
    )
    expect(input).not.toBeNull()
    input.nativeElement.value = 'duplicate'
    input.nativeElement.dispatchEvent(new Event('input'))
    jest.advanceTimersByTime(150)
    fixture.detectChanges()
    expect(component.filterText).toEqual('duplicate')
    expect(component.tasksForSection(TaskSection.NeedsAttention)).toHaveLength(
      2
    )
  })

  it('should prefer explicit reason in the result message', () => {
    expect(
      component.taskResultMessage({
        ...tasks[0],
        result_data: { reason: 'Manual review required', duplicate_of: 311 },
      })
    ).toBe('Manual review required')
  })

  it('should return null preview and popover text when there is no result message', () => {
    expect(component.taskResultPreview(tasks[2])).toBeNull()
    expect(component.taskResultPopoverMessage(tasks[2])).toBe('')
    expect(component.taskResultMessageOverflowsPopover(tasks[2])).toBe(false)
  })

  it('should navigate to a duplicate document details page', () => {
    const routerSpy = jest.spyOn(router, 'navigate')

    component.openDuplicateDocument(99)

    expect(routerSpy).toHaveBeenCalledWith(['documents', 99, 'details'])
  })

  it('should report when a result message overflows the popover limit', () => {
    const longMessage = 'x'.repeat(350)
    const task = {
      ...tasks[0],
      result_data: { error_message: longMessage },
    }

    expect(component.taskResultPopoverMessage(task)).toBe(
      longMessage.slice(0, 300)
    )
    expect(component.taskResultMessageOverflowsPopover(task)).toBe(true)
  })

  it('should support keyboard events for filtering', () => {
    fixture.detectChanges()
    const input = fixture.debugElement.query(
      By.css('.task-search input[type=text]')
    )
    expect(input).not.toBeNull()
    input.nativeElement.value = '191092'
    input.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Enter' })
    )
    expect(component.filterText).toEqual('191092')
    input.nativeElement.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'Escape' })
    )
    expect(component.filterText).toEqual('')
  })

  it('should keep clearing selection independent from resetting filters', () => {
    component.setTaskType(PaperlessTaskType.ConsumeFile)
    component.toggleSelected(tasks[0])
    expect(component.selectedTasks.size).toBe(1)

    component.clearSelection()

    expect(component.selectedTasks.size).toBe(0)
    expect(component.selectedTaskType).toBe(PaperlessTaskType.ConsumeFile)
    expect(component.isFiltered).toBe(true)
  })
})
