import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { tap } from 'rxjs'
import { ConsumptionTemplate } from 'src/app/data/consumption-template'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class ConsumptionTemplateService extends AbstractPaperlessService<ConsumptionTemplate> {
  loading: boolean

  constructor(http: HttpClient) {
    super(http, 'consumption_templates')
  }

  public reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.templates = r.results
      this.loading = false
    })
  }

  private templates: ConsumptionTemplate[] = []

  public get allTemplates(): ConsumptionTemplate[] {
    return this.templates
  }

  create(o: ConsumptionTemplate) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: ConsumptionTemplate) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: ConsumptionTemplate) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
