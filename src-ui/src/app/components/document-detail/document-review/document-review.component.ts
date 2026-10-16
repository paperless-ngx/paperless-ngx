import { DatePipe, TitleCasePipe } from '@angular/common'
import { HttpErrorResponse } from '@angular/common/http'
import {
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  signal,
} from '@angular/core'
import { takeUntilDestroyed } from '@angular/core/rxjs-interop'
import { FormsModule } from '@angular/forms'
import { Subscription, forkJoin } from 'rxjs'
import {
  DocumentReview,
  ReviewAction,
  ReviewMutation,
  ReviewOptions,
} from 'src/app/data/document-review'
import { DocumentReviewService } from 'src/app/services/rest/document-review.service'
import { v4 as uuidv4 } from 'uuid'

@Component({
  selector: 'pngx-document-review',
  templateUrl: './document-review.component.html',
  imports: [FormsModule, DatePipe, TitleCasePipe],
})
export class DocumentReviewComponent {
  private readonly service = inject(DocumentReviewService)
  private readonly destroyRef = inject(DestroyRef)
  readonly documentId = input.required<number>()
  readonly documentModified = input<string>()
  readonly review = signal<DocumentReview>(null)
  readonly options = signal<ReviewOptions>({ allowed_actions: [], results: [] })
  readonly loading = signal(false)
  readonly busy = signal(false)
  readonly error = signal('')
  private readonly refresh = signal(0)
  private pendingMutation: ReviewMutation | null = null
  private reviewerSearch: Subscription
  private loadedDocument: number
  reviewer: number | null = null
  comment = ''
  search = ''

  constructor() {
    effect((cleanup) => {
      const documentId = this.documentId()
      this.documentModified()
      this.refresh()
      if (!documentId) return
      if (this.loadedDocument !== documentId) {
        this.loadedDocument = documentId
        this.pendingMutation = null
        this.reviewer = null
        this.comment = ''
        this.search = ''
        this.error.set('')
        this.busy.set(false)
        this.review.set(null)
      }
      this.loading.set(true)
      this.options.set({ allowed_actions: [], results: [] })
      const subscription = forkJoin({
        review: this.service.get(documentId),
        options: this.service.options(documentId),
      }).subscribe({
        next: ({ review, options }) => {
          this.review.set(review)
          this.options.set(options)
          this.loading.set(false)
        },
        error: () => {
          this.review.set(null)
          this.error.set(
            $localize`Unable to load review. Check your access and try again.`
          )
          this.loading.set(false)
        },
      })
      cleanup(() => {
        subscription.unsubscribe()
        this.reviewerSearch?.unsubscribe()
      })
    })
  }

  reload() {
    this.refresh.update((value) => value + 1)
  }

  can(action: ReviewAction) {
    return this.options().allowed_actions.includes(action)
  }

  searchReviewers() {
    const documentId = this.documentId()
    this.reviewerSearch?.unsubscribe()
    this.reviewerSearch = this.service
      .options(documentId, this.search)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (options) => {
          if (documentId === this.documentId()) this.options.set(options)
        },
        error: () => this.error.set($localize`Unable to find reviewers.`),
      })
  }

  get validComment() {
    const length = Array.from(this.comment.trim()).length
    return length >= 1 && length <= 2000
  }

  act(action: ReviewAction) {
    if (this.busy() || this.loading() || !this.can(action)) return
    if (action === 'submit' && this.reviewer === null) return
    if (action === 'reject' && !this.validComment) return
    const mutation: ReviewMutation = {
      action,
      expected_revision: this.review().revision,
      request_id: '',
    }
    if (action === 'submit') mutation.reviewer = this.reviewer
    if (action === 'reject') mutation.comment = this.comment.trim()
    const previousId = this.pendingMutation?.request_id
    mutation.request_id =
      previousId &&
      JSON.stringify(this.pendingMutation) ===
        JSON.stringify({ ...mutation, request_id: previousId })
        ? previousId
        : uuidv4()
    this.pendingMutation = mutation
    const documentId = this.documentId()
    this.reviewerSearch?.unsubscribe()
    this.busy.set(true)
    this.error.set('')
    this.service
      .mutate(documentId, mutation)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (review) => {
          if (documentId !== this.documentId()) return
          this.pendingMutation = null
          this.review.set(review)
          this.options.set({ allowed_actions: [], results: [] })
          this.comment = ''
          this.reviewer = null
          this.busy.set(false)
          this.reload()
        },
        error: (error: HttpErrorResponse) => {
          if (documentId !== this.documentId()) return
          this.busy.set(false)
          if (error.status === 409) {
            this.pendingMutation = null
            this.error.set(
              $localize`The review changed. The latest state has been loaded; check it before trying again.`
            )
            this.reload()
          } else if (
            error.status === 400 ||
            error.status === 403 ||
            error.status === 404
          ) {
            this.pendingMutation = null
            this.error.set(
              $localize`The action was not allowed. Check your permissions, reviewer and rejection comment.`
            )
            this.reload()
          } else {
            this.error.set(
              $localize`Unable to save review. Retry to safely reuse this request.`
            )
          }
        },
      })
  }
}
