import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { first, map } from 'rxjs/operators'
import { PaperlessTask } from 'src/app/data/paperless-task'
import { environment } from 'src/environments/environment'

interface TasksAPIResponse {
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
      .get<TasksAPIResponse>(`${this.baseUrl}consumption_tasks/`)
      .pipe(first())
      .subscribe((r) => {
        this.incompleteTasks = r.incomplete
        this.completedTasks = r.completed
        this.failedTasks = r.failed
        this.loading = false
        return true
      })
  }

  // private savedViews: PaperlessSavedView[] = []

  // get allViews() {
  //   return this.savedViews
  // }

  // get sidebarViews() {
  //   return this.savedViews.filter((v) => v.show_in_sidebar)
  // }

  // get dashboardViews() {
  //   return this.savedViews.filter((v) => v.show_on_dashboard)
  // }

  // create(o: PaperlessSavedView) {
  //   return super.create(o).pipe(tap(() => this.reload()))
  // }

  // update(o: PaperlessSavedView) {
  //   return super.update(o).pipe(tap(() => this.reload()))
  // }

  // patchMany(objects: PaperlessSavedView[]): Observable<PaperlessSavedView[]> {
  //   return combineLatest(objects.map((o) => super.patch(o))).pipe(
  //     tap(() => this.reload())
  //   )
  // }

  // delete(o: PaperlessSavedView) {
  //   return super.delete(o).pipe(tap(() => this.reload()))
  // }
}
