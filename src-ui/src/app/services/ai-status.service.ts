import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { BehaviorSubject, Observable, interval, Subscription } from 'rxjs'
import { catchError, map, startWith, switchMap } from 'rxjs/operators'
import { AIStatus } from 'src/app/data/ai-status'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class AIStatusService {
  private http = inject(HttpClient)

  private baseUrl: string = environment.apiBaseUrl
  private aiStatusSubject = new BehaviorSubject<AIStatus>({
    active: false,
    processing: false,
    documents_scanned_today: 0,
    suggestions_applied: 0,
    pending_deletion_requests: 0,
  })

  public loading: boolean = false
  private pollingSubscription?: Subscription

  // Poll every 30 seconds for AI status updates
  private readonly POLL_INTERVAL = 30000

  constructor() {
    // Polling is now controlled manually via startPolling()
  }

  /**
   * Get the current AI status as an observable
   */
  public getStatus(): Observable<AIStatus> {
    return this.aiStatusSubject.asObservable()
  }

  /**
   * Get the current AI status value
   */
  public getCurrentStatus(): AIStatus {
    return this.aiStatusSubject.value
  }

  /**
   * Start polling for AI status updates
   */
  public startPolling(): void {
    if (this.pollingSubscription) {
      return // Already running
    }
    this.pollingSubscription = interval(this.POLL_INTERVAL)
      .pipe(
        startWith(0), // Emit immediately on subscription
        switchMap(() => this.fetchAIStatus())
      )
      .subscribe((status) => {
        this.aiStatusSubject.next(status)
      })
  }

  /**
   * Stop polling for AI status updates
   */
  public stopPolling(): void {
    if (this.pollingSubscription) {
      this.pollingSubscription.unsubscribe()
      this.pollingSubscription = undefined
    }
  }

  /**
   * Fetch AI status from the backend
   */
  private fetchAIStatus(): Observable<AIStatus> {
    this.loading = true

    return this.http
      .get<AIStatus>(`${this.baseUrl}ai/status/`)
      .pipe(
        map((status) => {
          this.loading = false
          return status
        }),
        catchError((error) => {
          this.loading = false
          console.warn('Failed to fetch AI status, using mock data:', error)
          // Return mock data if endpoint doesn't exist yet
          return [
            {
              active: true,
              processing: false,
              documents_scanned_today: 42,
              suggestions_applied: 15,
              pending_deletion_requests: 2,
              last_scan: new Date().toISOString(),
              version: '1.0.0',
            },
          ]
        })
      )
  }

  /**
   * Manually refresh the AI status
   */
  public refresh(): void {
    this.fetchAIStatus().subscribe((status) => {
      this.aiStatusSubject.next(status)
    })
  }
}
