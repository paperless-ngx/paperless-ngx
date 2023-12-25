import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { tap } from 'rxjs'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { WorkflowTrigger } from 'src/app/data/workflow-trigger'

@Injectable({
  providedIn: 'root',
})
export class WorkflowTriggerService extends AbstractPaperlessService<WorkflowTrigger> {
  loading: boolean

  constructor(http: HttpClient) {
    super(http, 'workflow_triggers')
  }

  public reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.triggers = r.results
      this.loading = false
    })
  }

  private triggers: WorkflowTrigger[] = []

  public get allWorkflows(): WorkflowTrigger[] {
    return this.triggers
  }

  create(o: WorkflowTrigger) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: WorkflowTrigger) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: WorkflowTrigger) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
