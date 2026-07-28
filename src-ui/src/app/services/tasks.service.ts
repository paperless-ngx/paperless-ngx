import { HttpClient } from '@angular/common/http'
import { Injectable, inject, signal } from '@angular/core'
import { EMPTY, Observable, Subject } from 'rxjs'
import {
  catchError,
  finalize,
  first,
  map,
  switchMap,
  takeUntil,
  tap,
} from 'rxjs/operators'
import {
  PaperlessTask,
  PaperlessTaskStatus,
  PaperlessTaskStatusCounts,
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

  private readonly tasks = signal<PaperlessTask[]>([])
  private readonly reloadNotifier = new Subject<void>()

  private unsubscribeNotifer: Subject<any> = new Subject()

  constructor() {
    this.reloadNotifier
      .pipe(
        switchMap(() => {
          this.loading = true
          return this.http
            .get<Results<PaperlessTask>>(`${this.baseUrl}${this.endpoint}/`, {
              params: {
                acknowledged: 'false',
                page_size: this.defaultReloadPageSize,
              },
            })
            .pipe(
              map((response) => response.results),
              takeUntil(this.unsubscribeNotifer),
              catchError(() => EMPTY),
              finalize(() => {
                this.loading = false
              })
            )
        })
      )
      .subscribe((tasks) => {
        this.tasks.set(tasks)
      })
  }

  public get needsAttentionTasks(): PaperlessTask[] {
    return this.tasks().filter((t) =>
      [PaperlessTaskStatus.Failure, PaperlessTaskStatus.Revoked].includes(
        t.status
      )
    )
  }

  public reload() {
    this.reloadNotifier.next()
  }

  public list(
    page: number,
    pageSize: number,
    extraParams?: Record<string, string | number | boolean | readonly string[]>
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

  public statusCounts(
    extraParams?: Record<string, string | number | boolean | readonly string[]>
  ): Observable<PaperlessTaskStatusCounts> {
    return this.http.get<PaperlessTaskStatusCounts>(
      `${this.baseUrl}${this.endpoint}/status_counts/`,
      {
        params: extraParams,
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

  public dismissAllTasks(): Observable<any> {
    return this.http
      .post(`${this.baseUrl}tasks/acknowledge/`, {
        all: true,
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
