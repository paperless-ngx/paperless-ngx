import { JsonPipe, NgTemplateOutlet } from '@angular/common'
import { Component, inject, OnDestroy, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { Router, RouterLink } from '@angular/router'
import {
  NgbCollapseModule,
  NgbDropdownModule,
  NgbModal,
  NgbPaginationModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  debounceTime,
  distinctUntilChanged,
  filter,
  first,
  Subject,
  takeUntil,
  timer,
} from 'rxjs'
import {
  PaperlessTask,
  PaperlessTaskStatus,
  PaperlessTaskTriggerSource,
  PaperlessTaskType,
} from 'src/app/data/paperless-task'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { TasksService } from 'src/app/services/tasks.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

export enum TaskSection {
  All = 'all',
  NeedsAttention = 'needs_attention',
  InProgress = 'in_progress',
  Completed = 'completed',
}

enum TaskFilterTargetID {
  Name,
  Result,
}

const FILTER_TARGETS = [
  { id: TaskFilterTargetID.Name, name: $localize`Name` },
  { id: TaskFilterTargetID.Result, name: $localize`Result` },
]

const SECTION_LABELS = {
  [TaskSection.All]: $localize`All`,
  [TaskSection.NeedsAttention]: $localize`Needs attention`,
  [TaskSection.InProgress]: $localize`In progress`,
  [TaskSection.Completed]: $localize`Recently completed`,
}

const TASK_TYPE_OPTIONS: Array<{
  value: PaperlessTaskType
  label: string
}> = [
  {
    value: PaperlessTaskType.ConsumeFile,
    label: $localize`Consume File`,
  },
  {
    value: PaperlessTaskType.TrainClassifier,
    label: $localize`Train Classifier`,
  },
  {
    value: PaperlessTaskType.SanityCheck,
    label: $localize`Sanity Check`,
  },
  { value: PaperlessTaskType.MailFetch, label: $localize`Mail Fetch` },
  { value: PaperlessTaskType.LlmIndex, label: $localize`LLM Index` },
  {
    value: PaperlessTaskType.EmptyTrash,
    label: $localize`Empty Trash`,
  },
  {
    value: PaperlessTaskType.CheckWorkflows,
    label: $localize`Check Workflows`,
  },
  {
    value: PaperlessTaskType.BulkUpdate,
    label: $localize`Bulk Update`,
  },
  {
    value: PaperlessTaskType.ReprocessDocument,
    label: $localize`Reprocess Document`,
  },
  {
    value: PaperlessTaskType.BuildShareLink,
    label: $localize`Build Share Link`,
  },
  {
    value: PaperlessTaskType.BulkDelete,
    label: $localize`Bulk Delete`,
  },
]

const TRIGGER_SOURCE_OPTIONS: Array<{
  value: PaperlessTaskTriggerSource
  label: string
}> = [
  {
    value: PaperlessTaskTriggerSource.Scheduled,
    label: $localize`Scheduled`,
  },
  { value: PaperlessTaskTriggerSource.WebUI, label: $localize`Web UI` },
  {
    value: PaperlessTaskTriggerSource.ApiUpload,
    label: $localize`API Upload`,
  },
  {
    value: PaperlessTaskTriggerSource.FolderConsume,
    label: $localize`Folder Consume`,
  },
  {
    value: PaperlessTaskTriggerSource.EmailConsume,
    label: $localize`Email Consume`,
  },
  { value: PaperlessTaskTriggerSource.System, label: $localize`System` },
  { value: PaperlessTaskTriggerSource.Manual, label: $localize`Manual` },
]

@Component({
  selector: 'pngx-tasks',
  templateUrl: './tasks.component.html',
  styleUrls: ['./tasks.component.scss'],
  imports: [
    PageHeaderComponent,
    IfPermissionsDirective,
    CustomDatePipe,
    JsonPipe,
    FormsModule,
    ReactiveFormsModule,
    NgTemplateOutlet,
    RouterLink,
    NgbCollapseModule,
    NgbDropdownModule,
    NgbPaginationModule,
    NgbPopoverModule,
    NgxBootstrapIconsModule,
  ],
})
export class TasksComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  tasksService = inject(TasksService)
  private modalService = inject(NgbModal)
  private readonly router = inject(Router)
  private readonly toastService = inject(ToastService)

  readonly TaskSection = TaskSection
  readonly sections = [
    TaskSection.NeedsAttention,
    TaskSection.InProgress,
    TaskSection.Completed,
  ]
  public selectedTasks: Set<number> = new Set()
  public expandedTask: number
  public autoRefreshEnabled: boolean = true
  public readonly pageSize = 25
  public page: number = 1
  public totalTasks: number = 0
  public pagedTasks: PaperlessTask[] = []
  public selectedSection: TaskSection = TaskSection.All
  public selectedTaskType: PaperlessTaskType | null = null
  public selectedTriggerSource: PaperlessTaskTriggerSource | null = null

  private _filterText: string = ''
  get filterText() {
    return this._filterText
  }
  set filterText(value: string) {
    this.filterDebounce.next(value)
  }

  public filterTargetID: TaskFilterTargetID = TaskFilterTargetID.Name
  public get filterTargetName(): string {
    return FILTER_TARGETS.find((t) => t.id == this.filterTargetID).name
  }
  private filterDebounce: Subject<string> = new Subject<string>()

  public get filterTargets(): Array<{ id: number; name: string }> {
    return FILTER_TARGETS
  }

  public get taskTypeOptions(): Array<{
    value: PaperlessTaskType
    label: string
  }> {
    return TASK_TYPE_OPTIONS
  }

  public get triggerSourceOptions(): Array<{
    value: PaperlessTaskTriggerSource
    label: string
  }> {
    return TRIGGER_SOURCE_OPTIONS
  }

  public get selectedTaskTypeLabel(): string {
    if (this.selectedTaskType === null) {
      return $localize`All types`
    }

    return (
      this.taskTypeOptions.find(
        (option) => option.value === this.selectedTaskType
      )?.label ?? this.selectedTaskType
    )
  }

  public get selectedTriggerSourceLabel(): string {
    if (this.selectedTriggerSource === null) {
      return $localize`All sources`
    }

    return (
      this.triggerSourceOptions.find(
        (option) => option.value === this.selectedTriggerSource
      )?.label ?? this.selectedTriggerSource
    )
  }

  get dismissButtonText(): string {
    return this.selectedTasks.size > 0
      ? $localize`Dismiss selected`
      : $localize`Dismiss visible`
  }

  get visibleSections(): TaskSection[] {
    const sections =
      this.selectedSection === TaskSection.All
        ? this.sections
        : [this.selectedSection]

    return sections.filter(
      (section) => this.tasksForSection(section).length > 0
    )
  }

  get visibleTasks(): PaperlessTask[] {
    return this.visibleSections.flatMap((section) =>
      this.tasksForSection(section)
    )
  }

  get isFiltered(): boolean {
    return (
      this.selectedTaskType !== null ||
      this.selectedTriggerSource !== null ||
      this._filterText.length > 0
    )
  }

  ngOnInit() {
    this.tasksService.reload()
    this.reloadPage()
    timer(5000, 5000)
      .pipe(
        filter(() => this.autoRefreshEnabled),
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe(() => {
        this.tasksService.reload()
        this.reloadPage(false)
      })

    this.filterDebounce
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        debounceTime(100),
        distinctUntilChanged(),
        filter((query) => !query.length || query.length > 2)
      )
      .subscribe((query) => {
        this._filterText = query
        this.clearSelection()
      })
  }

  ngOnDestroy() {
    super.ngOnDestroy()
    this.tasksService.cancelPending()
  }

  dismissTask(task: PaperlessTask) {
    this.dismissTasks(task)
  }

  dismissTasks(task: PaperlessTask = undefined) {
    let tasks = task ? new Set([task.id]) : new Set(this.selectedTasks.values())
    if (!task && tasks.size == 0) {
      tasks = new Set(this.visibleTasks.map((t) => t.id))
    }

    if (tasks.size > 1) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm Dismiss`
      modal.componentInstance.messageBold = $localize`Dismiss ${tasks.size} tasks?`
      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Dismiss`
      modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        modal.close()
        this.tasksService.dismissTasks(tasks).subscribe({
          next: () => {
            this.reloadPage(false)
          },
          error: (e) => {
            this.toastService.showError($localize`Error dismissing tasks`, e)
            modal.componentInstance.buttonsEnabled = true
          },
        })
        this.clearSelection()
      })
    } else if (tasks.size === 1) {
      this.tasksService.dismissTasks(tasks).subscribe({
        next: () => {
          this.reloadPage(false)
        },
        error: (e) =>
          this.toastService.showError($localize`Error dismissing task`, e),
      })
      this.clearSelection()
    }
  }

  expandTask(task: PaperlessTask) {
    this.expandedTask = this.expandedTask == task.id ? undefined : task.id
  }

  toggleSelected(task: PaperlessTask) {
    this.selectedTasks.has(task.id)
      ? this.selectedTasks.delete(task.id)
      : this.selectedTasks.add(task.id)
  }

  toggleSection(section: TaskSection, event: PointerEvent) {
    const sectionTasks = this.tasksForSection(section)
    if ((event.target as HTMLInputElement).checked) {
      sectionTasks.forEach((task) => this.selectedTasks.add(task.id))
    } else {
      sectionTasks.forEach((task) => this.selectedTasks.delete(task.id))
    }
  }

  areAllSelected(tasks: PaperlessTask[]): boolean {
    return (
      tasks.length > 0 && tasks.every((task) => this.selectedTasks.has(task.id))
    )
  }

  taskDisplayName(task: PaperlessTask): string {
    return task.input_data?.filename?.toString() || task.task_type_display
  }

  taskShowsSeparateTypeLabel(task: PaperlessTask): boolean {
    return this.taskDisplayName(task) !== task.task_type_display
  }

  taskResultMessage(task: PaperlessTask): string | null {
    if (!task.result_data) {
      return null
    }

    const documentId = task.result_data?.['document_id']
    if (typeof documentId === 'number') {
      return $localize`Success. New document id ${documentId} created`
    }

    const reason = task.result_data?.['reason']
    if (typeof reason === 'string') {
      return reason
    }

    const duplicateOf = task.result_data?.['duplicate_of']
    if (typeof duplicateOf === 'number') {
      return $localize`Duplicate of document #${duplicateOf}`
    }

    const errorMessage = task.result_data?.['error_message']
    if (typeof errorMessage === 'string') {
      return errorMessage
    }

    return null
  }

  taskResultPreview(task: PaperlessTask): string | null {
    const message = this.taskResultMessage(task)
    if (!message) {
      return null
    }

    return message.length > 50 ? `${message.slice(0, 50)}...` : message
  }

  taskHasLongResultMessage(task: PaperlessTask): boolean {
    return (this.taskResultMessage(task)?.length ?? 0) > 50
  }

  taskHasResultMessage(task: PaperlessTask): boolean {
    return !!this.taskResultMessage(task)
  }

  duplicateDocumentId(task: PaperlessTask): number | null {
    const duplicateOf = task.result_data?.['duplicate_of']
    return typeof duplicateOf === 'number' ? duplicateOf : null
  }

  duplicateTaskLabel(task: PaperlessTask): string {
    return $localize`Duplicate of document #${this.duplicateDocumentId(task)}`
  }

  openDuplicateDocument(documentId: number) {
    this.router.navigate(['documents', documentId, 'details'])
  }

  taskResultPopoverMessage(task: PaperlessTask): string {
    return this.taskResultMessage(task)?.slice(0, 300) ?? ''
  }

  taskResultMessageOverflowsPopover(task: PaperlessTask): boolean {
    return (this.taskResultMessage(task)?.length ?? 0) > 300
  }

  tasksForSection(section: TaskSection): PaperlessTask[] {
    let tasks = this.pagedTasks.filter((task) =>
      this.taskBelongsToSection(task, section)
    )

    return tasks.filter((task) => this.taskMatchesCurrentFilters(task))
  }

  sectionLabel(section: TaskSection): string {
    return SECTION_LABELS[section]
  }

  sectionCount(section: TaskSection): number {
    return this.pagedTasks.filter((task) =>
      this.taskBelongsToSection(task, section)
    ).length
  }

  sectionShowsResults(section: TaskSection): boolean {
    return section !== TaskSection.InProgress
  }

  setSection(section: TaskSection) {
    this.selectedSection = section
    this.clearSelection()
  }

  setTaskType(taskType: PaperlessTaskType | null) {
    this.selectedTaskType = taskType
    this.clearSelection()
  }

  setTriggerSource(triggerSource: PaperlessTaskTriggerSource | null) {
    this.selectedTriggerSource = triggerSource
    this.clearSelection()
  }

  taskTypeOptionCount(taskType: PaperlessTaskType | null): number {
    return this.tasksForOptionCounts({ taskType }).length
  }

  triggerSourceOptionCount(
    triggerSource: PaperlessTaskTriggerSource | null
  ): number {
    return this.tasksForOptionCounts({ triggerSource }).length
  }

  isTaskTypeOptionDisabled(taskType: PaperlessTaskType | null): boolean {
    return this.taskTypeOptionCount(taskType) === 0
  }

  isTriggerSourceOptionDisabled(
    triggerSource: PaperlessTaskTriggerSource | null
  ): boolean {
    return this.triggerSourceOptionCount(triggerSource) === 0
  }

  clearSelection() {
    this.selectedTasks.clear()
  }

  setPage(page: number) {
    if (this.page === page) {
      return
    }

    this.page = page
    this.clearSelection()
    this.reloadPage()
  }

  public resetFilter() {
    this._filterText = ''
  }

  public resetFilters() {
    this.selectedTaskType = null
    this.selectedTriggerSource = null
    this.resetFilter()
    this.clearSelection()
  }

  filterInputKeyup(event: KeyboardEvent) {
    if (event.key == 'Enter') {
      this._filterText = (event.target as HTMLInputElement).value
    } else if (event.key === 'Escape') {
      this.resetFilter()
    }
  }

  private taskBelongsToSection(
    task: PaperlessTask,
    section: TaskSection
  ): boolean {
    switch (section) {
      case TaskSection.NeedsAttention:
        return [
          PaperlessTaskStatus.Failure,
          PaperlessTaskStatus.Revoked,
        ].includes(task.status)
      case TaskSection.InProgress:
        return [
          PaperlessTaskStatus.Pending,
          PaperlessTaskStatus.Started,
        ].includes(task.status)
      case TaskSection.Completed:
        return task.status === PaperlessTaskStatus.Success
    }
  }

  private taskMatchesCurrentFilters(task: PaperlessTask): boolean {
    return this.taskMatchesFilters(task, {
      taskType: this.selectedTaskType,
      triggerSource: this.selectedTriggerSource,
    })
  }

  private taskMatchesFilters(
    task: PaperlessTask,
    {
      taskType,
      triggerSource,
    }: {
      taskType: PaperlessTaskType | null
      triggerSource: PaperlessTaskTriggerSource | null
    }
  ): boolean {
    if (taskType !== null && task.task_type !== taskType) {
      return false
    }

    if (triggerSource !== null && task.trigger_source !== triggerSource) {
      return false
    }

    if (!this._filterText.length) {
      return true
    }

    const query = this._filterText.toLowerCase()

    if (this.filterTargetID == TaskFilterTargetID.Name) {
      return [
        this.taskDisplayName(task),
        task.task_type_display,
        task.trigger_source_display,
      ]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query))
    }

    return this.taskResultMessage(task)?.toLowerCase().includes(query) ?? false
  }

  private tasksForOptionCounts({
    taskType = this.selectedTaskType,
    triggerSource = this.selectedTriggerSource,
  }: {
    taskType?: PaperlessTaskType | null
    triggerSource?: PaperlessTaskTriggerSource | null
  }): PaperlessTask[] {
    const sections =
      this.selectedSection === TaskSection.All
        ? this.sections
        : [this.selectedSection]

    return this.pagedTasks.filter(
      (task) =>
        sections.some((section) => this.taskBelongsToSection(task, section)) &&
        this.taskMatchesFilters(task, { taskType, triggerSource })
    )
  }

  private reloadPage(resetToFirstPage: boolean = false) {
    if (resetToFirstPage) {
      this.page = 1
    }

    this.loading = true
    this.tasksService
      .list(this.page, this.pageSize, { acknowledged: false })
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.pagedTasks = result.results
          this.totalTasks = result.count
          this.loading = false
          if (
            this.page > 1 &&
            this.pagedTasks.length === 0 &&
            this.totalTasks > 0
          ) {
            this.page -= 1
            this.reloadPage()
          }
        },
        error: () => {
          this.loading = false
        },
      })
  }
}
