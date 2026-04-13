import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { OcrTemplate } from '../../data/ocr-template'
import { AbstractPaperlessService } from './abstract-paperless-service'

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
}
