import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable, Subject } from 'rxjs'
import { first, map, takeUntil, tap } from 'rxjs/operators'
import {
  PaperlessTask,
  PaperlessTaskStatus,
  PaperlessTaskType,
} from 'src/app/data/paperless-task'
import { Results } from 'src/app/data/results'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class TasksService {
  private http = inject(HttpClient)

  private baseUrl: string = environment.apiBaseUrl
  private endpoint: string = 'tasks'
  private readonly defaultReloadPageSize = 1000

  public loading: boolean = false

  private fileTasks: PaperlessTask[] = []

  private unsubscribeNotifer: Subject<any> = new Subject()

  public get total(): number {
    return this.fileTasks.length
  }

  public get allFileTasks(): PaperlessTask[] {
    return this.fileTasks.slice(0)
  }

  public get queuedFileTasks(): PaperlessTask[] {
    return this.fileTasks.filter(
      (t) => t.status === PaperlessTaskStatus.Pending
    )
  }

  public get startedFileTasks(): PaperlessTask[] {
    return this.fileTasks.filter(
      (t) => t.status === PaperlessTaskStatus.Started
    )
  }

  public get completedFileTasks(): PaperlessTask[] {
    return this.fileTasks.filter(
      (t) => t.status === PaperlessTaskStatus.Success
    )
  }

  public get failedFileTasks(): PaperlessTask[] {
    return this.fileTasks.filter(
      (t) => t.status === PaperlessTaskStatus.Failure
    )
  }

  public get needsAttentionTasks(): PaperlessTask[] {
    return this.fileTasks.filter((t) =>
      [PaperlessTaskStatus.Failure, PaperlessTaskStatus.Revoked].includes(
        t.status
      )
    )
  }

  public reload() {
    if (this.loading) return
    this.loading = true

    this.http
      .get<Results<PaperlessTask>>(`${this.baseUrl}${this.endpoint}/`, {
        params: {
          acknowledged: 'false',
          page_size: this.defaultReloadPageSize,
        },
      })
      .pipe(map((r) => r.results))
      .pipe(takeUntil(this.unsubscribeNotifer), first())
      .subscribe((r) => {
        this.fileTasks = r
        this.loading = false
      })
  }

  public list(
    page: number,
    pageSize: number,
    extraParams?: Record<string, string | number | boolean>
  ): Observable<Results<PaperlessTask>> {
    return this.http.get<Results<PaperlessTask>>(
      `${this.baseUrl}${this.endpoint}/`,
      {
        params: {
          page,
          page_size: pageSize,
          ...extraParams,
        },
      }
    )
  }

  public dismissTasks(task_ids: Set<number>): Observable<any> {
    return this.http
      .post(`${this.baseUrl}tasks/acknowledge/`, {
        tasks: [...task_ids],
      })
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifer),
        tap(() => {
          this.reload()
        })
      )
  }

  public cancelPending(): void {
    this.unsubscribeNotifer.next(true)
  }

  public run(taskType: PaperlessTaskType): Observable<{ task_id: string }> {
    return this.http.post<{ task_id: string }>(
      `${environment.apiBaseUrl}${this.endpoint}/run/`,
      { task_type: taskType }
    )
  }
}
