import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { DocumentAction } from 'src/app/data/document-action'
import { Document } from 'src/app/data/document'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class DocumentActionsService extends AbstractPaperlessService<DocumentAction> {
  constructor() {
    super()
    this.resourceName = 'documents'
  }

  getApplicableActions(documentId: number): Observable<DocumentAction[]> {
    return this.http.get<DocumentAction[]>(
      this.getResourceUrl(documentId, 'actions')
    )
  }

  trigger(documentId: number, triggerId: number): Observable<Document> {
    return this.http.post<Document>(
      this.getResourceUrl(documentId, 'actions'),
      {
        trigger: triggerId,
      }
    )
  }
}
