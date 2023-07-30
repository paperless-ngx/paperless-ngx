import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { PaperlessIndexFieldMetadata } from 'src/app/data/paperless-document-index-field-metadata'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class DocumentMetadataService extends AbstractPaperlessService<PaperlessIndexFieldMetadata> {
  constructor(http: HttpClient) {
    super(http, 'documents')
  }

  getMetadatas(documentId: number): Observable<PaperlessIndexFieldMetadata[]> {
    return this.http.get<PaperlessIndexFieldMetadata[]>(
      this.getResourceUrl(documentId, 'index_field_metadata')
    )
  }

   updateMetadata(
    id: number,
    data: string
  ): Observable<PaperlessIndexFieldMetadata[]> {
    return this.http.post<PaperlessIndexFieldMetadata[]>(
      this.getResourceUrl(id, 'index_field_metadata'),
      { metadata: data }
    )
  }
}
