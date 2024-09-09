import { Component, OnInit, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { PaperlessTask } from 'src/app/data/paperless-task'
import { TasksService } from 'src/app/services/tasks.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-tasks',
  templateUrl: './tasks.component.html',
  styleUrls: ['./tasks.component.scss'],
})
export class TasksComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  public activeTab: string
  public selectedTasks: Set<number> = new Set()
  public togggleAll: boolean = false
  public expandedTask: number

  public pageSize: number = 25
  public page: number = 1

  public autoRefreshInterval: any

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
    this.toggleAutoRefresh()
  }

  ngOnDestroy() {
    this.tasksService.cancelPending()
    clearInterval(this.autoRefreshInterval)
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
        this.tasksService.reload()
      }, 5000)
    }
  }
}
