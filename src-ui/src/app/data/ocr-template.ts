import { ObjectWithId } from './object-with-id'

export type OcrZoneTarget = 'custom_field' | 'title' | 'asn' | 'created'
export type OcrBuiltinTarget = Exclude<OcrZoneTarget, 'custom_field'>
export type OcrZoneTransform =
  | 'none'
  | 'strip'
  | 'uppercase'
  | 'lowercase'
  | 'numeric'
  | 'strip_punctuation'
  | 'date'
  | 'qr_code'

export const OCR_ZONE_TARGET = {
  CustomField: 'custom_field',
  Title: 'title',
  Asn: 'asn',
  Created: 'created',
} as const satisfies Record<string, OcrZoneTarget>

export const OCR_ZONE_TRANSFORM = {
  None: 'none',
  Strip: 'strip',
  Uppercase: 'uppercase',
  Lowercase: 'lowercase',
  Numeric: 'numeric',
  StripPunctuation: 'strip_punctuation',
  Date: 'date',
  QrCode: 'qr_code',
} as const satisfies Record<string, OcrZoneTransform>

export const DEFAULT_OCR_ZONE_TARGET = OCR_ZONE_TARGET.CustomField
export const DEFAULT_OCR_ZONE_TRANSFORM = OCR_ZONE_TRANSFORM.Strip
export const DEFAULT_OCR_ZONE_LANGUAGE = 'deu+eng'

export function isOcrBuiltinTarget(value: unknown): value is OcrBuiltinTarget {
  return (
    value === OCR_ZONE_TARGET.Title ||
    value === OCR_ZONE_TARGET.Asn ||
    value === OCR_ZONE_TARGET.Created
  )
}

export const OCR_BUILTIN_TARGETS = [
  { id: OCR_ZONE_TARGET.Title, name: $localize`Title` },
  { id: OCR_ZONE_TARGET.Asn, name: $localize`Archive serial number` },
  { id: OCR_ZONE_TARGET.Created, name: $localize`Date created` },
]

export interface OcrTemplateZone {
  id?: number
  name: string
  target?: OcrZoneTarget
  custom_field: number | null
  page?: number
  x: number
  y: number
  width: number
  height: number
  ocr_language: string
  transform: OcrZoneTransform
  date_format?: string
  validation_regex: string
  order: number
  zone_source_width?: number
  zone_source_height?: number
}

export const TRANSFORM_OPTIONS = [
  { id: OCR_ZONE_TRANSFORM.None, name: $localize`None` },
  { id: OCR_ZONE_TRANSFORM.Strip, name: $localize`Strip whitespace` },
  { id: OCR_ZONE_TRANSFORM.Uppercase, name: $localize`Uppercase` },
  { id: OCR_ZONE_TRANSFORM.Lowercase, name: $localize`Lowercase` },
  { id: OCR_ZONE_TRANSFORM.Numeric, name: $localize`Numeric only` },
  {
    id: OCR_ZONE_TRANSFORM.StripPunctuation,
    name: $localize`Remove leading/trailing punctuation`,
  },
  { id: OCR_ZONE_TRANSFORM.Date, name: $localize`Parse date` },
  { id: OCR_ZONE_TRANSFORM.QrCode, name: $localize`Read QR/barcode` },
]

export const OCR_LANGUAGE_OPTIONS = [
  { id: 'eng', name: $localize`English` },
  { id: 'deu', name: $localize`German` },
  { id: 'fra', name: $localize`French` },
  { id: 'ita', name: $localize`Italian` },
  { id: 'spa', name: $localize`Spanish` },
  { id: 'por', name: $localize`Portuguese` },
  { id: 'nld', name: $localize`Dutch` },
]

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
  combine_formats?: Record<string, string>
  created?: string
  updated?: string
  zones: OcrTemplateZone[]
}

export interface ZoneTestRequest {
  name: string
  x: number
  y: number
  width: number
  height: number
  page: number
  ocr_language: string
  transform: OcrZoneTransform
  date_format?: string
  validation_regex: string
  zone_source_width?: number
  zone_source_height?: number
}

export interface OcrZoneTestResult {
  raw_text?: string | null
  value?: string | null
  regex?: string
  regex_match?: boolean | null
  error?: string
}

export interface OcrZoneRunResult {
  template: string
  zone: string
  custom_field: string
  value: string | number | null
}
