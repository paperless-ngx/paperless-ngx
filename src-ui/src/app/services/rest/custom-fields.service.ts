import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { Observable } from 'rxjs'
import { PaperlessCustomField } from 'src/app/data/paperless-custom-field'

@Injectable({
  providedIn: 'root',
})
export class CustomFieldsService extends AbstractPaperlessService<PaperlessCustomField> {
  constructor(http: HttpClient) {
    super(http, 'documents')
  }

  getFields(documentId: number): Observable<PaperlessCustomField[]> {
    return this.http.get<PaperlessCustomField[]>(
      this.getResourceUrl(documentId, 'custom_metadata')
    )
  }

  addField(
    documentId: number,
    field: PaperlessCustomField
  ): Observable<PaperlessCustomField[]> {
    return this.http.post<PaperlessCustomField[]>(
      this.getResourceUrl(documentId, 'custom_metadata'),
      field
    )
  }

  // deleteField(
  //   documentId: number,
  //   fieldId: number
  // ): Observable<PaperlessCustomField[]> {
  //   return this.http.delete<PaperlessCustomField[]>(
  //     this.getResourceUrl(documentId, 'custom_metadata'),
  //     { params: new HttpParams({ fromString: `id=${fieldId}` }) }
  //   )
  // }
}
