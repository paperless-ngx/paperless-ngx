import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { first, map } from 'rxjs/operators'
import { PaperlessTask } from 'src/app/data/paperless-task'
import { environment } from 'src/environments/environment'

interface TasksAPIResponse {
  total: number
  incomplete: Array<PaperlessTask>
  completed: Array<PaperlessTask>
  failed: Array<PaperlessTask>
}

@Injectable({
  providedIn: 'root',
})
export class TasksService {
  private baseUrl: string = environment.apiBaseUrl

  loading: boolean

  public total: number

  private incompleteTasks: PaperlessTask[] = []
  public get incomplete(): PaperlessTask[] {
    return this.incompleteTasks
  }

  private completedTasks: PaperlessTask[] = []
  public get completed(): PaperlessTask[] {
    return this.completedTasks
  }

  private failedTasks: PaperlessTask[] = []
  public get failed(): PaperlessTask[] {
    return this.failedTasks
  }

  constructor(private http: HttpClient) {}

  public reload() {
    this.loading = true

    this.http
      .get<TasksAPIResponse>(`${this.baseUrl}tasks/`)
      .pipe(first())
      .subscribe((r) => {
        this.total = r.total
        this.incompleteTasks = r.incomplete
        this.completedTasks = r.completed
        this.failedTasks = r.failed
        this.loading = false
        return true
      })
  }

  public dismissTasks(task_ids: Set<number>) {
    this.http
      .post(`${this.baseUrl}acknowledge_tasks/`, {
        tasks: [...task_ids],
      })
      .pipe(first())
      .subscribe((r) => {
        this.reload()
      })
  }
}
