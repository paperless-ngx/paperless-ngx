import { NgTemplateOutlet } from '@angular/common'
import { Component, inject, OnDestroy, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import {
  NgbCollapseModule,
  NgbDropdownModule,
  NgbModal,
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
import { PaperlessTask, PaperlessTaskStatus } from 'src/app/data/paperless-task'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { TasksService } from 'src/app/services/tasks.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

export enum TaskSection {
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

export const ALL_TASK_SECTIONS = 'all'

const SECTION_LABELS: Record<TaskSection, string> = {
  [TaskSection.NeedsAttention]: $localize`Needs attention`,
  [TaskSection.InProgress]: $localize`In progress`,
  [TaskSection.Completed]: $localize`Recently completed`,
}

@Component({
  selector: 'pngx-tasks',
  templateUrl: './tasks.component.html',
  styleUrls: ['./tasks.component.scss'],
  imports: [
    PageHeaderComponent,
    IfPermissionsDirective,
    CustomDatePipe,
    FormsModule,
    ReactiveFormsModule,
    NgTemplateOutlet,
    NgbCollapseModule,
    NgbDropdownModule,
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
  readonly allTaskSections = ALL_TASK_SECTIONS
  public selectedTasks: Set<number> = new Set()
  public expandedTask: number
  public autoRefreshEnabled: boolean = true
  public selectedSection: TaskSection | typeof ALL_TASK_SECTIONS =
    ALL_TASK_SECTIONS

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

  get dismissButtonText(): string {
    return this.selectedTasks.size > 0
      ? $localize`Dismiss selected`
      : $localize`Dismiss visible`
  }

  get visibleSections(): TaskSection[] {
    const sections =
      this.selectedSection === ALL_TASK_SECTIONS
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

  ngOnInit() {
    this.tasksService.reload()
    timer(5000, 5000)
      .pipe(
        filter(() => this.autoRefreshEnabled),
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe(() => {
        this.tasksService.reload()
      })

    this.filterDebounce
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        debounceTime(100),
        distinctUntilChanged(),
        filter((query) => !query.length || query.length > 2)
      )
      .subscribe((query) => (this._filterText = query))
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
          error: (e) => {
            this.toastService.showError($localize`Error dismissing tasks`, e)
            modal.componentInstance.buttonsEnabled = true
          },
        })
        this.clearSelection()
      })
    } else if (tasks.size === 1) {
      this.tasksService.dismissTasks(tasks).subscribe({
        error: (e) =>
          this.toastService.showError($localize`Error dismissing task`, e),
      })
      this.clearSelection()
    }
  }

  dismissAndGo(task: PaperlessTask) {
    this.dismissTask(task)
    this.router.navigate(['documents', task.related_document_ids?.[0]])
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

  tasksForSection(section: TaskSection): PaperlessTask[] {
    let tasks = this.tasksService.allFileTasks.filter((task) =>
      this.taskBelongsToSection(task, section)
    )

    if (this._filterText.length) {
      tasks = tasks.filter((task) => {
        if (this.filterTargetID == TaskFilterTargetID.Name) {
          return this.taskDisplayName(task)
            ?.toLowerCase()
            .includes(this._filterText.toLowerCase())
        } else if (this.filterTargetID == TaskFilterTargetID.Result) {
          return task.result_message
            ?.toLowerCase()
            .includes(this._filterText.toLowerCase())
        }
      })
    }

    return tasks
  }

  sectionLabel(section: TaskSection): string {
    return SECTION_LABELS[section]
  }

  sectionCount(section: TaskSection): number {
    return this.tasksService.allFileTasks.filter((task) =>
      this.taskBelongsToSection(task, section)
    ).length
  }

  sectionShowsResults(section: TaskSection): boolean {
    return section !== TaskSection.InProgress
  }

  setSection(section: TaskSection | typeof ALL_TASK_SECTIONS) {
    this.selectedSection = section
    this.clearSelection()
  }

  clearSelection() {
    this.selectedTasks.clear()
  }

  public resetFilter() {
    this._filterText = ''
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
}
