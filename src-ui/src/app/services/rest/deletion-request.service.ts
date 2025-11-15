import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { tap, catchError } from 'rxjs/operators'
import { DeletionRequest } from 'src/app/data/deletion-request'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class DeletionRequestService extends AbstractPaperlessService<DeletionRequest> {
  constructor() {
    super()
    this.resourceName = 'deletion_requests'
  }

  /**
   * Approve a deletion request
   * @param id The ID of the deletion request
   * @param reviewComment Optional comment for the approval
   * @returns Observable of the updated deletion request
   */
  approve(id: number, reviewComment?: string): Observable<DeletionRequest> {
    this._loading = true
    const body = reviewComment ? { review_comment: reviewComment } : {}
    return this.http
      .post<DeletionRequest>(this.getResourceUrl(id, 'approve'), body)
      .pipe(
        tap(() => {
          this._loading = false
        }),
        catchError((error) => {
          this._loading = false
          throw error
        })
      )
  }

  /**
   * Reject a deletion request
   * @param id The ID of the deletion request
   * @param reviewComment Optional comment for the rejection
   * @returns Observable of the updated deletion request
   */
  reject(id: number, reviewComment?: string): Observable<DeletionRequest> {
    this._loading = true
    const body = reviewComment ? { review_comment: reviewComment } : {}
    return this.http
      .post<DeletionRequest>(this.getResourceUrl(id, 'reject'), body)
      .pipe(
        tap(() => {
          this._loading = false
        }),
        catchError((error) => {
          this._loading = false
          throw error
        })
      )
  }

  /**
   * Get the count of pending deletion requests
   * @returns Observable with the count
   */
  getPendingCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(
      this.getResourceUrl(null, 'pending_count')
    )
  }
}
