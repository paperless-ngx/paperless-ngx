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
