import { TitleCasePipe } from '@angular/common'
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core'
import { takeUntilDestroyed } from '@angular/core/rxjs-interop'
import { FormsModule } from '@angular/forms'
import { RouterLink } from '@angular/router'
import { Subject, catchError, of, switchMap } from 'rxjs'
import { ReviewQueue, ReviewState } from 'src/app/data/document-review'
import { DocumentReviewService } from 'src/app/services/rest/document-review.service'

@Component({
  selector: 'pngx-review-queue',
  templateUrl: './review-queue.component.html',
  imports: [FormsModule, RouterLink, TitleCasePipe],
})
export class ReviewQueueComponent implements OnInit {
  private readonly service = inject(DocumentReviewService)
  private readonly destroyRef = inject(DestroyRef)
  readonly queue = signal<ReviewQueue>({ count: 0, results: [] })
  readonly loading = signal(false)
  readonly error = signal('')
  state: ReviewState | '' = 'pending'
  reviewer: number | null = null
  page = 1
  private readonly requests = new Subject<void>()

  ngOnInit() {
    // Switching requests prevents an older filter response overwriting a newer one.
    this.requests
      .pipe(
        switchMap(() =>
          this.service.queue(this.state, this.reviewer, this.page).pipe(
            catchError(() => {
              this.error.set(
                $localize`Unable to load the review queue. Check filters and permissions.`
              )
              return of({ count: 0, results: [] })
            })
          )
        ),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe({
        next: (queue) => {
          this.queue.set(queue)
          this.loading.set(false)
        },
      })
    this.load()
  }

  load(resetPage = false) {
    if (
      this.reviewer !== null &&
      (!Number.isInteger(this.reviewer) || this.reviewer <= 0)
    ) {
      this.error.set($localize`Enter a positive reviewer ID or leave it empty.`)
      return
    }
    if (resetPage) this.page = 1
    this.error.set('')
    this.loading.set(true)
    this.requests.next()
  }

  nextPage(delta: number) {
    this.page += delta
    this.load()
  }
}
