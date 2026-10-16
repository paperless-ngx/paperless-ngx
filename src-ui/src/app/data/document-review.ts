export type ReviewState = 'unreviewed' | 'pending' | 'approved' | 'rejected'
export type ReviewAction = 'submit' | 'approve' | 'reject' | 'reopen'

export interface ReviewEvent {
  action: ReviewAction | 'invalidate'
  actor: number | null
  revision: number
  at: string
  request_id: string | null
  comment: string
}

export interface DocumentReview {
  document: number
  state: ReviewState
  revision: number
  reviewer: number | null
  submitted_by: number | null
  history: ReviewEvent[]
}

export interface ReviewMutation {
  action: ReviewAction
  expected_revision: number
  request_id: string
  reviewer?: number
  comment?: string
}

export interface ReviewOptions {
  allowed_actions: ReviewAction[]
  results: { id: number; username: string }[]
}

export interface ReviewQueue {
  count: number
  results: {
    document: number
    state: ReviewState
    reviewer: number | null
    revision: number
    title?: string
  }[]
}
