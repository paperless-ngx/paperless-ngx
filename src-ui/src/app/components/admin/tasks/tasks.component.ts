import { Component, OnDestroy, OnInit } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import {
  debounceTime,
  distinctUntilChanged,
  filter,
  first,
  Subject,
  takeUntil,
  timer,
} from 'rxjs'
import { PaperlessTask } from 'src/app/data/paperless-task'
import { TasksService } from 'src/app/services/tasks.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

export enum TaskTab {
  Queued = 'queued',
  Started = 'started',
  Completed = 'completed',
  Failed = 'failed',
}

enum TaskFilterTargetID {
  Name,
  Result,
}

const FILTER_TARGETS = [
  { id: TaskFilterTargetID.Name, name: $localize`Name` },
  { id: TaskFilterTargetID.Result, name: $localize`Result` },
]

@Component({
  selector: 'pngx-tasks',
  templateUrl: './tasks.component.html',
  styleUrls: ['./tasks.component.scss'],
})
export class TasksComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  public activeTab: TaskTab
  public selectedTasks: Set<number> = new Set()
  public togggleAll: boolean = false
  public expandedTask: number

  public pageSize: number = 25
  public page: number = 1

  public autoRefreshEnabled: boolean = true

  private _filterText: string = ''
  get filterText() {
    return this._filterText
  }
  set filterText(value: string) {
    this.filterDebounce.next(value)
  }

  public filterTargetID: TaskFilterTargetID = TaskFilterTargetID.Name
  public get filterTargetName(): string {
    return this.filterTargets.find((t) => t.id == this.filterTargetID).name
  }
  private filterDebounce: Subject<string> = new Subject<string>()

  public get filterTargets(): Array<{ id: number; name: string }> {
    return [TaskTab.Failed, TaskTab.Completed].includes(this.activeTab)
      ? FILTER_TARGETS
      : FILTER_TARGETS.slice(0, 1)
  }

  get dismissButtonText(): string {
    return this.selectedTasks.size > 0
      ? $localize`Dismiss selected`
      : $localize`Dismiss all`
  }

  constructor(
    public tasksService: TasksService,
    private modalService: NgbModal,
    private readonly router: Router
  ) {
    super()
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
    if (!task && tasks.size == 0)
      tasks = new Set(this.tasksService.allFileTasks.map((t) => t.id))
    if (tasks.size > 1) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm Dismiss All`
      modal.componentInstance.messageBold = $localize`Dismiss all ${tasks.size} tasks?`
      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Dismiss`
      modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        modal.close()
        this.tasksService.dismissTasks(tasks)
        this.clearSelection()
      })
    } else {
      this.tasksService.dismissTasks(tasks)
      this.clearSelection()
    }
  }

  dismissAndGo(task: PaperlessTask) {
    this.dismissTask(task)
    this.router.navigate(['documents', task.related_document])
  }

  expandTask(task: PaperlessTask) {
    this.expandedTask = this.expandedTask == task.id ? undefined : task.id
  }

  toggleSelected(task: PaperlessTask) {
    this.selectedTasks.has(task.id)
      ? this.selectedTasks.delete(task.id)
      : this.selectedTasks.add(task.id)
  }

  get currentTasks(): PaperlessTask[] {
    let tasks: PaperlessTask[] = []
    switch (this.activeTab) {
      case TaskTab.Queued:
        tasks = this.tasksService.queuedFileTasks
        break
      case TaskTab.Started:
        tasks = this.tasksService.startedFileTasks
        break
      case TaskTab.Completed:
        tasks = this.tasksService.completedFileTasks
        break
      case TaskTab.Failed:
        tasks = this.tasksService.failedFileTasks
        break
    }
    if (this._filterText.length) {
      tasks = tasks.filter((t) => {
        if (this.filterTargetID == TaskFilterTargetID.Name) {
          return t.task_file_name
            .toLowerCase()
            .includes(this._filterText.toLowerCase())
        } else if (this.filterTargetID == TaskFilterTargetID.Result) {
          return t.result.toLowerCase().includes(this._filterText.toLowerCase())
        }
      })
    }
    return tasks
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedTasks = new Set(this.currentTasks.map((t) => t.id))
    } else {
      this.clearSelection()
    }
  }

  clearSelection() {
    this.togggleAll = false
    this.selectedTasks.clear()
  }

  duringTabChange() {
    this.page = 1
  }

  beforeTabChange() {
    this.resetFilter()
    this.filterTargetID = TaskFilterTargetID.Name
  }

  get activeTabLocalized(): string {
    switch (this.activeTab) {
      case TaskTab.Queued:
        return $localize`queued`
      case TaskTab.Started:
        return $localize`started`
      case TaskTab.Completed:
        return $localize`completed`
      case TaskTab.Failed:
        return $localize`failed`
    }
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
}
