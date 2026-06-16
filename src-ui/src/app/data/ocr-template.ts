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
  date_format?: string
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
  { id: 'strip_punctuation', name: $localize`Remove leading/trailing punctuation` },
  { id: 'date', name: $localize`Parse date` },
  { id: 'qr_code', name: $localize`Read QR/barcode` },
]

// Common Tesseract OCR languages for the zone language picker.
export const OCR_LANGUAGE_OPTIONS = [
  { id: 'eng', name: $localize`English` },
  { id: 'deu', name: $localize`German` },
  { id: 'fra', name: $localize`French` },
  { id: 'ita', name: $localize`Italian` },
  { id: 'spa', name: $localize`Spanish` },
  { id: 'por', name: $localize`Portuguese` },
  { id: 'nld', name: $localize`Dutch` },
]

// Date-format presets for the "Parse date" transform. Values are Python
// strptime format strings; '' = auto-detect. "Custom" is offered in the UI.
export const DATE_FORMAT_OPTIONS = [
  { id: '', name: $localize`Auto-detect` },
  { id: '%d.%m.%Y', name: 'DD.MM.YYYY' },
  { id: '%Y/%m/%d', name: 'YYYY/MM/DD' },
  { id: '%d/%m/%Y', name: 'DD/MM/YYYY' },
]

export interface OcrTemplate extends ObjectWithId {
  name: string
  document_type: number
  sample_document: number | null
  source_width: number
  source_height: number
  enabled: boolean
  created?: string
  updated?: string
  zones: OcrTemplateZone[]
}

// Ad-hoc zone passed to the per-zone test endpoint (no id, just geometry + OCR opts).
export interface ZoneTestRequest {
  name: string
  x: number
  y: number
  width: number
  height: number
  page: number
  ocr_language: string
  transform: string
  date_format?: string
  validation_regex: string
  zone_source_width?: number
  zone_source_height?: number
}

// Response of the per-zone test: raw OCR text, transformed value, regex outcome.
export interface OcrZoneTestResult {
  raw_text?: string | null
  value?: string | null
  regex?: string
  regex_match?: boolean | null
  error?: string
}

// One row of the run-zone-ocr response (per zone across the doc-type's templates).
export interface OcrZoneRunResult {
  template: string
  zone: string
  custom_field: string
  value: string | number | null
}
