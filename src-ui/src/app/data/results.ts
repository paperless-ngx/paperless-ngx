import { Document } from './document'

export interface Results<T> {
  count: number

  display_count?: number

  results: T[]
}

export interface SelectionDataItem {
  id: number
  document_count: number
}

export interface SelectionData {
  selected_storage_paths: SelectionDataItem[]
  selected_correspondents: SelectionDataItem[]
  selected_tags: SelectionDataItem[]
  selected_document_types: SelectionDataItem[]
  selected_custom_fields: SelectionDataItem[]
}

export interface DocumentResults extends Results<Document> {
  selection_data?: SelectionData
}
