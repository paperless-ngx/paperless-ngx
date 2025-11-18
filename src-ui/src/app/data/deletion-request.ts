import { ObjectWithId } from './object-with-id'

export interface DeletionRequestDocument {
  id: number
  title: string
  created: string
  correspondent?: string
  document_type?: string
  tags: string[]
}

export interface FailedDeletion {
  document_id: number
  document_title: string
  error: string
}

export interface CompletionDetails {
  deleted_count: number
  deleted_document_ids: number[]
  failed_deletions?: FailedDeletion[]
  errors?: string[]
  total_documents: number
  completed_at: string
}

export interface DeletionRequestImpactSummary {
  document_count: number
  documents: DeletionRequestDocument[]
  affected_tags: Array<{ id: number; name: string; count: number }> | string[]
  affected_correspondents:
    | Array<{ id: number; name: string; count: number }>
    | string[]
  affected_types: Array<{ id: number; name: string; count: number }> | string[]
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
  completion_details?: CompletionDetails
}
