import { ObjectWithId } from './object-with-id'

export interface OcrTemplateZone {
  id?: number
  name: string
  custom_field: number
  page?: number
  x: number
  y: number
  width: number
  height: number
  ocr_language: string
  transform: string
  order: number
  zone_source_width?: number
  zone_source_height?: number
}

export const TRANSFORM_OPTIONS = [
  { id: 'none', name: $localize`None` },
  { id: 'strip', name: $localize`Strip whitespace` },
  { id: 'uppercase', name: $localize`Uppercase` },
  { id: 'lowercase', name: $localize`Lowercase` },
  { id: 'numeric', name: $localize`Numeric only` },
  { id: 'date_dmy', name: $localize`Parse date (DD.MM.YYYY)` },
  { id: 'date_ymd', name: $localize`Parse date (YYYY-MM-DD)` },
  { id: 'date_auto', name: $localize`Parse date (auto-detect)` },
]

export interface OcrTemplate extends ObjectWithId {
  name: string
  document_type: number
  sample_document: number | null
  default_page: number
  source_width: number
  source_height: number
  enabled: boolean
  created?: string
  updated?: string
  zones: OcrTemplateZone[]
}
