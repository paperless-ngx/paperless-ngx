import { HttpClient } from '@angular/common/http'
import { Injectable, inject, signal } from '@angular/core'
import { EMPTY, Observable, Subject } from 'rxjs'
import {
  catchError,
  finalize,
  first,
  switchMap,
  takeUntil,
  tap,
} from 'rxjs/operators'
import {
  PaperlessTask,
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

  public loading: boolean = false

  private readonly tasksStatusCounts = signal<PaperlessTaskStatusCounts>({
    all: 0,
    needs_attention: 0,
    in_progress: 0,
    completed: 0,
  })
  private readonly reloadNotifier = new Subject<void>()

  private unsubscribeNotifer: Subject<any> = new Subject()

  constructor() {
    this.reloadNotifier
      .pipe(switchMap(() => this.fetchUnacknowledgedTasksCounts()))
      .subscribe((taskStatusCounts) => {
        this.tasksStatusCounts.set(taskStatusCounts)
      })
  }

  private fetchUnacknowledgedTasksCounts(): Observable<PaperlessTaskStatusCounts> {
    this.loading = true
    return this.statusCounts({ acknowledged: false }).pipe(
      takeUntil(this.unsubscribeNotifer),
      catchError(() => EMPTY),
      finalize(() => {
        this.loading = false
      })
    )
  }

  public get needsAttentionTasksCount(): number {
    return this.tasksStatusCounts().needs_attention
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
      .post(`${this.baseUrl}${this.endpoint}/acknowledge/`, {
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
      .post(`${this.baseUrl}${this.endpoint}/acknowledge/`, {
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
