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
  private unsubscribeNotifer = new Subject()

  constructor(public tasksService: TasksService) {}

  ngOnInit() {
    this.tasksService.reload()
  }

  ngOnDestroy() {
    this.unsubscribeNotifer.next(true)
  }

  acknowledgeTask(task: PaperlessTask) {
    throw new Error('Not implemented' + task)
  }
}
