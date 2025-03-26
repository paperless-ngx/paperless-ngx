import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { AbstractEdocService } from './abstract-edoc-service'
import { Observable } from 'rxjs'
import { DocumentApproval } from 'src/app/data/document-approval'

@Injectable({
  providedIn: 'root',
})
export class DocumentApprovalsService extends AbstractEdocService<DocumentApproval> {
  constructor(http: HttpClient) {
    super(http, 'documents')
  }

  getApprovals(documentId: number): Observable<DocumentApproval[]> {
    return this.http.get<DocumentApproval[]>(
      this.getResourceUrl(documentId, 'approvals')
    )
  }

  addApproval(id: number, approval: string): Observable<DocumentApproval[]> {
    return this.http.post<DocumentApproval[]>(this.getResourceUrl(id, 'approvals'), {
      approval: approval,
    })
  }

  updateApproval(documentId: number, approvalId: number): Observable<DocumentApproval[]> {
    return this.http.put<DocumentApproval[]>(
      this.getResourceUrl(documentId, 'approvals'),
      { params: new HttpParams({ fromString: `id=${approvalId}` }) }
    )
  }
}
