import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { tap } from 'rxjs'
import { Workflow } from 'src/app/data/workflow'
import { AbstractEdocService } from './abstract-edoc-service'

@Injectable({
  providedIn: 'root',
})
export class WorkflowService extends AbstractEdocService<Workflow> {
  loading: boolean

  constructor(http: HttpClient) {
    super(http, 'workflows')
  }

  public reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.workflows = r.results
      this.loading = false
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
