import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import {
  DocumentReview,
  ReviewMutation,
  ReviewOptions,
  ReviewQueue,
  ReviewState,
} from 'src/app/data/document-review'
import { environment } from 'src/environments/environment'

@Injectable({ providedIn: 'root' })
export class DocumentReviewService {
  private readonly http = inject(HttpClient)
  private readonly baseUrl = environment.apiBaseUrl

  get(document: number) {
    return this.http.get<DocumentReview>(
      `${this.baseUrl}documents/${document}/review/`
    )
  }

  mutate(document: number, payload: ReviewMutation) {
    return this.http.post<DocumentReview>(
      `${this.baseUrl}documents/${document}/review/`,
      payload
    )
  }

  options(document: number, search = '') {
    return this.http.get<ReviewOptions>(
      `${this.baseUrl}documents/${document}/reviewers/`,
      { params: new HttpParams().set('search', search) }
    )
  }

  queue(state: ReviewState | '', reviewer: number | null, page = 1) {
    let params = new HttpParams().set('page', page).set('page_size', 20)
    if (state) params = params.set('state', state)
    if (reviewer !== null) params = params.set('reviewer', reviewer)
    return this.http.get<ReviewQueue>(`${this.baseUrl}review_queue/`, {
      params,
    })
  }
}
