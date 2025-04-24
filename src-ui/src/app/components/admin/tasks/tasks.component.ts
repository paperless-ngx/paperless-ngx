import { Component, OnInit, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { delay, first, Observable, tap } from 'rxjs'
import { EdocTask } from 'src/app/data/edoc-task'
import { TasksService } from 'src/app/services/tasks.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { Results } from '../../../data/results'

@Component({
  selector: 'pngx-tasks',
  templateUrl: './tasks.component.html',
  styleUrls: ['./tasks.component.scss'],
})
export class TasksComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy {
  public activeTab: string
  public selectedTasks: Set<number> = new Set()
  public togggleAll: boolean = false
  public expandedTask: number

  public pageSize: number = 25
  public page: number = 1

  public autoRefreshInterval: any
  public tasksQueued: Results<EdocTask> = {
    count: 0,
    results: [],
    all: [],
  }
  public tasksStarted: Results<EdocTask> = {
    count: 0,
    results: [],
    all: [],
  }
  public tasksCompleted: Results<EdocTask> = {
    count: 0,
    results: [],
    all: [],
  }

  public tasksFailed: Results<EdocTask> = {
    count: 0,
    results: [],
    all: [],
  }

  // public tasksCurrent: EdocTask[] = []
  public tasksCurrent: Results<EdocTask> = {
    count: 0,
    results: [],
    all: [],
  }

  get dismissButtonText(): string {
    return this.selectedTasks.size > 0
      ? $localize`Dismiss selected`
      : $localize`Dismiss all`
  }

  constructor(
    public tasksService: TasksService,
    private modalService: NgbModal,
    private readonly router: Router,
  ) {
    super()
  }

  ngOnInit() {
    // this.tasksService.reload()
    this.reloadData()
    this.toggleAutoRefresh()
  }

  ngOnDestroy() {
    this.tasksService.cancelPending()
    clearInterval(this.autoRefreshInterval)
  }

  removeTask(task_ids: Set<number>) {
    this.tasksCurrent.results = this.tasksCurrent.results.filter(
      task => !task_ids.has(task.id),
    )
    this.tasksCurrent.all = this.tasksCurrent.all.filter(
      task => !task_ids.has(task),
    )
  }

  dismissTask(task: EdocTask) {
    this.dismissTasks(task)
  }

  dismissTasks(task: EdocTask = undefined) {
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
        this.removeTask(tasks)
        this.tasksService.dismissTasks(tasks)
        this.selectedTasks.clear()
      })
    } else {
      this.removeTask(tasks)
      this.tasksService.dismissTasks(tasks)
      this.selectedTasks.clear()
    }
  }

  dismissAndGo(task: EdocTask) {
    this.dismissTask(task)
    this.router.navigate(['documents', task.related_document])
  }

  expandTask(task: EdocTask) {
    this.expandedTask = this.expandedTask == task.id ? undefined : task.id
  }

  toggleSelected(task: EdocTask) {
    this.selectedTasks.has(task.id)
      ? this.selectedTasks.delete(task.id)
      : this.selectedTasks.add(task.id)
  }

  get currentTasks(): EdocTask[] {
    let tasks: EdocTask[] = []
    switch (this.activeTab) {
      case 'queued':
        tasks = this.tasksService.queuedFileTasks
        break
      case 'started':
        tasks = this.tasksService.startedFileTasks
        break
      case 'completed':
        tasks = this.tasksService.completedFileTasks
        break
      case 'failed':
        tasks = this.tasksService.failedFileTasks
        break
    }
    return tasks
  }


  currentDataEdocTasks() {
    switch (this.activeTab) {
      case 'queued':
        if (this.page == 1) {
          this.tasksCurrent = this.tasksQueued
          break
        }
        this.queuedFileEdocTasks(this.page)

        break
      case 'started':
        if (this.page == 1) {

          break
        }
        this.startedFileEdocTasks(this.page)

        break
      case 'completed':
        if (this.page == 1) {
          this.tasksCurrent = this.tasksCompleted
          break
        }
        this.completedFileEdocTasks(this.page)

        break
      case 'failed':
        if (this.page == 1) {
          this.tasksCurrent = this.tasksFailed
          break
        }
        this.failedFileEdocTasks(this.page)
        break
    }
  }

  SetCurrentDataEdocTasks() {
    switch (this.activeTab) {
      case 'queued':
        this.tasksCurrent = this.tasksQueued
        break
      case 'started':
        this.tasksCurrent = this.tasksStarted
        break
      case 'completed':
        this.tasksCurrent = this.tasksCompleted
        break
      case 'failed':
        this.tasksCurrent = this.tasksFailed
        break
    }
  }

  toggleAll(event: PointerEvent) {
    this.SetCurrentDataEdocTasks()
    if ((event.target as HTMLInputElement).checked) {
      this.selectedTasks = new Set(this.tasksCurrent.all.map((t) => t))
    } else {
      this.clearSelection()
    }
  }

  clearSelection() {
    this.togggleAll = false
    this.selectedTasks.clear()
  }

  duringTabChange(navID: number) {
    this.page = 1
  }

  get activeTabLocalized(): string {
    switch (this.activeTab) {
      case 'queued':
        return $localize`queued`
      case 'started':
        return $localize`started`
      case 'completed':
        return $localize`completed`
      case 'failed':
        return $localize`failed`
    }
  }

  toggleAutoRefresh(): void {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval)
      this.autoRefreshInterval = null
    } else {
      this.autoRefreshInterval = setInterval(() => {
        // this.tasksService.reload()
        this.reloadData()
      }, 5000)
    }
  }

  reloadData() {
    this.queuedFileEdocTasks(1)
    this.startedFileEdocTasks(1)
    this.completedFileEdocTasks(1)
    this.failedFileEdocTasks(1)
    // this.currentDataEdocTasks();
  }

  queuedFileEdocTasks(pageQueue = 1) {
    this.tasksService
      .queuedFileEdocTasks(pageQueue)
      .pipe(
        tap((r) => {
          this.tasksQueued = r
          this.SetCurrentDataEdocTasks()
        }),
        // delay(100)
      )
      .subscribe(() => {
      })
  }

  startedFileEdocTasks(pageQueue = 1) {
    this.tasksService
      .startedFileEdocTasks(this.page)
      .pipe(
        tap((r) => {
          this.tasksStarted = r
          this.SetCurrentDataEdocTasks()
        }),
        // delay(100)
      )
      .subscribe(() => {
      })
  }

  completedFileEdocTasks(pageQueue = 1) {
    this.tasksService
      .completedFileEdocTasks(this.page)
      .pipe(
        tap((r) => {
          this.tasksCompleted = r
          this.SetCurrentDataEdocTasks()
        }),
        // delay(100)
      )
      .subscribe(() => {
      })
  }

  failedFileEdocTasks(pageQueue = 1) {
    this.tasksService
      .failedFileEdocTasks(this.page)
      .pipe(
        tap((r) => {
          this.tasksFailed = r
          this.SetCurrentDataEdocTasks()
        }),
        // delay(100)
      )
      .subscribe(() => {
      })
  }

  getCountTaskAll() {

    switch (this.activeTab) {
      case 'queued':
        return this.tasksQueued.count
      case 'started':
        return this.tasksStarted.count
      case 'completed':
        return this.tasksCompleted.count
      case 'failed':
        return this.tasksFailed.count
    }

  }

  onPageChange($event: number) {
    this.currentDataEdocTasks()
  }
}
