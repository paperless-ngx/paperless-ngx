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
    super(http, 'custom_fields')
  }

  // getFields(documentId: number): Observable<PaperlessCustomField[]> {
  //   return this.http.get<PaperlessCustomField[]>(
  //     this.getResourceUrl(documentId, 'custom_fields')
  //   )
  // }

  // addField(
  //   documentId: number,
  //   field: PaperlessCustomField
  // ): Observable<PaperlessCustomField[]> {
  //   return this.http.post<PaperlessCustomField[]>(
  //     this.getResourceUrl(documentId, 'custom_fields'),
  //     field
  //   )
  // }

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
