import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { PaperlessDocumentComment } from 'src/app/data/paperless-document-comment'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { Observable } from 'rxjs'

@Injectable({
  providedIn: 'root',
})
export class DocumentCommentsService extends AbstractPaperlessService<PaperlessDocumentComment> {
  constructor(http: HttpClient) {
    super(http, 'documents')
  }

  getComments(documentId: number): Observable<PaperlessDocumentComment[]> {
    return this.http.get<PaperlessDocumentComment[]>(
      this.getResourceUrl(documentId, 'comments')
    )
  }

  addComment(id: number, comment): Observable<PaperlessDocumentComment[]> {
    return this.http.post<PaperlessDocumentComment[]>(
      this.getResourceUrl(id, 'comments'),
      { comment: comment }
    )
  }

  deleteComment(
    documentId: number,
    commentId: number
  ): Observable<PaperlessDocumentComment[]> {
    return this.http.delete<PaperlessDocumentComment[]>(
      this.getResourceUrl(documentId, 'comments'),
      { params: new HttpParams({ fromString: `id=${commentId}` }) }
    )
  }
}
