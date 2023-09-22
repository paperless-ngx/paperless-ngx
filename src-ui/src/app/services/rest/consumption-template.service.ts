import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { tap } from 'rxjs'
import { PaperlessConsumptionTemplate } from 'src/app/data/paperless-consumption-template'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class ConsumptionTemplateService extends AbstractPaperlessService<PaperlessConsumptionTemplate> {
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

  private templates: PaperlessConsumptionTemplate[] = []

  public get allTemplates(): PaperlessConsumptionTemplate[] {
    return this.templates
  }

  create(o: PaperlessConsumptionTemplate) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: PaperlessConsumptionTemplate) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: PaperlessConsumptionTemplate) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
