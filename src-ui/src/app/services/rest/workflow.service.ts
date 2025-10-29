import { Injectable } from '@angular/core'
import { tap } from 'rxjs'
import { Workflow } from 'src/app/data/workflow'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class WorkflowService extends AbstractPaperlessService<Workflow> {
  constructor() {
    super()
    this.resourceName = 'workflows'
  }

  public reload() {
    this._loading = true
    this.listAll().subscribe((r) => {
      this.workflows = r.results
      this._loading = false
    })
  }

  private workflows: Workflow[] = []

  public get allWorkflows(): Workflow[] {
    return this.workflows
  }

  create(o: Workflow) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: Workflow) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: Workflow) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
