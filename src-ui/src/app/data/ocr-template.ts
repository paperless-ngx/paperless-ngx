import { ObjectWithId } from './object-with-id'

export const OCR_BUILTIN_TARGETS = [
  { id: 'title', name: $localize`Title` },
  { id: 'asn', name: $localize`Archive serial number` },
  { id: 'created', name: $localize`Date created` },
]

export interface OcrTemplateZone {
  id?: number
  name: string
  target?: string // 'custom_field' | 'title' | 'asn' | 'created'
  custom_field: number | null
  page?: number
  x: number
  y: number
  width: number
  height: number
  ocr_language: string
  transform: string
  validation_regex: string
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
  { id: 'qr_code', name: $localize`Read QR/barcode` },
  { id: 'qr_code_raw', name: $localize`Read QR/barcode (raw)` },
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
