import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'
import { first, takeUntil } from 'rxjs/operators'
import {
  EdocTask,
  EdocTaskStatus,
  EdocTaskType,
} from 'src/app/data/edoc-task'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class TasksService {
  private baseUrl: string = environment.apiBaseUrl

  public loading: boolean

  private fileTasks: EdocTask[] = []

  private unsubscribeNotifer: Subject<any> = new Subject()

  public get total(): number {
    return this.fileTasks.length
  }

  public get allFileTasks(): EdocTask[] {
    return this.fileTasks.slice(0)
  }

  public get queuedFileTasks(): EdocTask[] {
    return this.fileTasks.filter((t) => t.status == EdocTaskStatus.Pending)
  }

  public get startedFileTasks(): EdocTask[] {
    return this.fileTasks.filter((t) => t.status == EdocTaskStatus.Started)
  }

  public get completedFileTasks(): EdocTask[] {
    return this.fileTasks.filter(
      (t) => t.status == EdocTaskStatus.Complete
    )
  }

  public get failedFileTasks(): EdocTask[] {
    return this.fileTasks.filter((t) => t.status == EdocTaskStatus.Failed)
  }

  constructor(private http: HttpClient) {}

  public reload() {
    this.loading = true

    this.http
      .get<EdocTask[]>(`${this.baseUrl}tasks/`)
      .pipe(takeUntil(this.unsubscribeNotifer), first())
      .subscribe((r) => {
        this.fileTasks = r.filter((t) => t.type == EdocTaskType.File) // they're all File tasks, for now
        this.loading = false
      })
  }

  public dismissTasks(task_ids: Set<number>) {
    this.http
      .post(`${this.baseUrl}acknowledge_tasks/`, {
        tasks: [...task_ids],
      })
      .pipe(takeUntil(this.unsubscribeNotifer), first())
      .subscribe((r) => {
        this.reload()
      })
  }

  public cancelPending(): void {
    this.unsubscribeNotifer.next(true)
  }
}
