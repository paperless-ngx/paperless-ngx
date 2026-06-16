import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { tap } from 'rxjs/operators'
import { OcrTemplate } from '../../data/ocr-template'
import { AbstractPaperlessService } from './abstract-paperless-service'

export interface QuickCreateFieldResult {
  id: number
  name: string
  data_type: string
  created: boolean
}

@Injectable({ providedIn: 'root' })
export class OcrTemplateService extends AbstractPaperlessService<OcrTemplate> {
  constructor() {
    super()
    this.resourceName = 'ocr_templates'
  }

  getPageImageUrl(docId: number, page: number): string {
    return `${this.baseUrl}${this.resourceName}/document-page-image/${docId}/${page}/`
  }

  testExtraction(templateId: number, docId: number): Observable<any> {
    return this.http.post(
      this.getResourceUrl(templateId, `test/${docId}`),
      {}
    )
  }

  testZone(docId: number, zone: any): Observable<any> {
    return this.http.post(
      `${this.baseUrl}${this.resourceName}/test-zone/`,
      { document: docId, zone }
    )
  }

  quickCreateField(name: string, dataType: string): Observable<QuickCreateFieldResult> {
    return this.http.post<QuickCreateFieldResult>(
      `${this.baseUrl}${this.resourceName}/quick-create-field/`,
      { name, data_type: dataType }
    )
  }
}
