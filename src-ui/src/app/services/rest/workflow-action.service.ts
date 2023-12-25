import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { tap } from 'rxjs'
import { Workflow } from 'src/app/data/workflow'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { WorkflowAction } from 'src/app/data/workflow-action'

@Injectable({
  providedIn: 'root',
})
export class WorkflowActionService extends AbstractPaperlessService<WorkflowAction> {
  loading: boolean

  constructor(http: HttpClient) {
    super(http, 'workflow_actions')
  }

  public reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.actions = r.results
      this.loading = false
    })
  }

  private actions: WorkflowAction[] = []

  public get allActions(): WorkflowAction[] {
    return this.actions
  }

  create(o: WorkflowAction) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: WorkflowAction) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: WorkflowAction) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
