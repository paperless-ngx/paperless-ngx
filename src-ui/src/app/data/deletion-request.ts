import { ObjectWithId } from './object-with-id'

export interface DeletionRequestDocument {
  id: number
  title: string
  created: string
  correspondent?: string
  document_type?: string
  tags: string[]
}

export interface DeletionRequestImpactSummary {
  document_count: number
  documents: DeletionRequestDocument[]
  affected_tags: string[]
  affected_correspondents: string[]
  affected_types: string[]
  date_range?: {
    earliest: string
    latest: string
  }
}

export enum DeletionRequestStatus {
  Pending = 'pending',
  Approved = 'approved',
  Rejected = 'rejected',
  Cancelled = 'cancelled',
  Completed = 'completed',
}

export interface DeletionRequest extends ObjectWithId {
  created_at: string
  updated_at: string
  requested_by_ai: boolean
  ai_reason: string
  user: number
  user_username: string
  status: DeletionRequestStatus
  documents: number[]
  documents_detail: DeletionRequestDocument[]
  document_count: number
  impact_summary: DeletionRequestImpactSummary
  reviewed_at?: string
  reviewed_by?: number
  reviewed_by_username?: string
  review_comment?: string
  completed_at?: string
  completion_details?: any
}
