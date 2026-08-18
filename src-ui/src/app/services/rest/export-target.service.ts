import { Injectable } from '@angular/core'
import { ExportTarget } from 'src/app/data/export-target'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class ExportTargetService extends AbstractPaperlessService<ExportTarget> {
  constructor() {
    super()
    this.resourceName = 'export_targets'
  }

  test(o: ExportTarget) {
    const target = Object.assign({}, o)
    delete target['set_permissions']
    return this.http.post<{ success: boolean }>(
      this.getResourceUrl() + 'test/',
      target
    )
  }
}
