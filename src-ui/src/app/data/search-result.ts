import { PaperlessDocument } from './paperless-document'

export class SearchHitHighlight {
  text?: string
  term?: number
}

export interface SearchHit {
  id?: number
  title?: string
  score?: number
  rank?: number

  highlights?: SearchHitHighlight[][]
  document?: PaperlessDocument
}

export interface SearchResult {

  count?: number
  page?: number
  page_count?: number

  corrected_query?: string

  results?: SearchHit[]


}
