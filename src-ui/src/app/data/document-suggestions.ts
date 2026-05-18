export interface DocumentSuggestions {
  title?: string

  tags?: number[]
  suggested_tags?: string[]

  correspondents?: number[]
  suggested_correspondents?: string[]

  document_types?: number[]
  suggested_document_types?: string[]

  storage_paths?: number[]
  suggested_storage_paths?: string[]

  dates?: string[] // ISO-formatted date string e.g. 2022-11-03
}
