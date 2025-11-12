/**
 * Represents the AI scanner status and statistics
 */
export interface AIStatus {
  /**
   * Whether the AI scanner is currently active/enabled
   */
  active: boolean

  /**
   * Whether the AI scanner is currently processing documents
   */
  processing: boolean

  /**
   * Number of documents scanned today
   */
  documents_scanned_today: number

  /**
   * Number of AI suggestions applied
   */
  suggestions_applied: number

  /**
   * Number of pending deletion requests awaiting user approval
   */
  pending_deletion_requests: number

  /**
   * Last scan timestamp (ISO format)
   */
  last_scan?: string

  /**
   * AI scanner version or configuration info
   */
  version?: string
}

/**
 * Represents a pending deletion request initiated by AI
 */
export interface DeletionRequest {
  id: number
  document_id: number
  document_title: string
  reason: string
  confidence: number
  created_at: string
  status: DeletionRequestStatus
}

/**
 * Status of a deletion request
 */
export enum DeletionRequestStatus {
  Pending = 'pending',
  Approved = 'approved',
  Rejected = 'rejected',
  Cancelled = 'cancelled',
  Completed = 'completed',
}
