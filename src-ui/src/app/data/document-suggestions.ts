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

const union = <T>(a: T[] = [], b: T[] = []): T[] => [...new Set([...a, ...b])]

export function mergeSuggestions(
  a: DocumentSuggestions,
  b: DocumentSuggestions
): DocumentSuggestions {
  if (!a) return b
  return {
    title: a.title || b.title,
    tags: union(a.tags, b.tags),
    suggested_tags: union(a.suggested_tags, b.suggested_tags),
    correspondents: union(a.correspondents, b.correspondents),
    suggested_correspondents: union(
      a.suggested_correspondents,
      b.suggested_correspondents
    ),
    document_types: union(a.document_types, b.document_types),
    suggested_document_types: union(
      a.suggested_document_types,
      b.suggested_document_types
    ),
    storage_paths: union(a.storage_paths, b.storage_paths),
    suggested_storage_paths: union(
      a.suggested_storage_paths,
      b.suggested_storage_paths
    ),
    dates: union(a.dates, b.dates),
  }
}
