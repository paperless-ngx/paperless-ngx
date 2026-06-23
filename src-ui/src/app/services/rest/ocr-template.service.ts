import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import {
  OcrTemplate,
  OcrZoneTestResult,
  ZoneTestRequest,
} from '../../data/ocr-template'
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

  testZone(
    docId: number,
    zone: ZoneTestRequest
  ): Observable<OcrZoneTestResult> {
    return this.http.post<OcrZoneTestResult>(
      `${this.baseUrl}${this.resourceName}/test-zone/`,
      { document: docId, zone }
    )
  }

  quickCreateField(
    name: string,
    dataType: string
  ): Observable<QuickCreateFieldResult> {
    return this.http.post<QuickCreateFieldResult>(
      `${this.baseUrl}${this.resourceName}/quick-create-field/`,
      { name, data_type: dataType }
    )
  }
}
