import { Component, OnInit, OnDestroy } from '@angular/core'
import { takeUntil, Subject } from 'rxjs'
import { PaperlessTask } from 'src/app/data/paperless-task'
import { TasksService } from 'src/app/services/tasks.service'

@Component({
  selector: 'app-tasks',
  templateUrl: './tasks.component.html',
  styleUrls: ['./tasks.component.scss'],
})
export class TasksComponent implements OnInit, OnDestroy {
  public activeTab: string
  public selectedTasks: Set<number> = new Set()
  private unsubscribeNotifer = new Subject()

  get dismissButtonText(): string {
    return this.selectedTasks.size > 0
      ? $localize`Dismiss selected`
      : $localize`Dismiss all`
  }

  constructor(public tasksService: TasksService) {}

  ngOnInit() {
    this.tasksService.reload()
  }

  ngOnDestroy() {
    this.unsubscribeNotifer.next(true)
  }

  dismissTask(task: PaperlessTask) {
    this.dismissTasks(task)
  }

  dismissTasks(task: PaperlessTask = undefined) {
    this.tasksService.dismissTasks(
      task ? new Set([task.id]) : this.selectedTasks
    )
  }

  toggleSelected(task: PaperlessTask) {
    this.selectedTasks.has(task.id)
      ? this.selectedTasks.delete(task.id)
      : this.selectedTasks.add(task.id)
  }

  get currentTasks(): PaperlessTask[] {
    let tasks: PaperlessTask[]
    switch (this.activeTab) {
      case 'incomplete':
        tasks = this.tasksService.incomplete
        break
      case 'completed':
        tasks = this.tasksService.completed
        break
      case 'failed':
        tasks = this.tasksService.failed
        break
      default:
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
    this.selectedTasks = new Set()
  }
}
