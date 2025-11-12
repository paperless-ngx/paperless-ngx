export enum AISuggestionType {
  Tag = 'tag',
  Correspondent = 'correspondent',
  DocumentType = 'document_type',
  StoragePath = 'storage_path',
  CustomField = 'custom_field',
  Date = 'date',
  Title = 'title',
}

export enum AISuggestionStatus {
  Pending = 'pending',
  Applied = 'applied',
  Rejected = 'rejected',
}

export interface AISuggestion {
  id: string
  type: AISuggestionType
  value: any
  confidence: number
  status: AISuggestionStatus
  label?: string
  field_name?: string // For custom fields
  created_at?: Date
}

export interface AIDocumentSuggestions {
  document_id: number
  suggestions: AISuggestion[]
  generated_at: Date
}
