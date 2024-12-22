export interface DocumentSuggestions {
  tags?: number[]

  correspondents?: number[]

  document_types?: number[]

  archive_fonts?: number[]

  storage_paths?: number[]

  warehouses?: number[]

  dates?: string[] // ISO-formatted date string e.g. 2022-11-03
}
