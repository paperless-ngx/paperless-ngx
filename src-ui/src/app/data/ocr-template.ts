import { CustomFieldDataType } from './custom-field'
import { MatchingModel } from './matching-model'
import { ObjectWithPermissions } from './object-with-permissions'

export enum OcrZoneTarget {
  CustomField = 'custom_field',
  Title = 'title',
  Asn = 'asn',
  Created = 'created',
}

export enum OcrZoneTransform {
  None = 'none',
  Strip = 'strip',
  Uppercase = 'uppercase',
  Lowercase = 'lowercase',
  Numeric = 'numeric',
  StripPunctuation = 'strip_punctuation',
  Date = 'date',
  QrCode = 'qr_code',
}

export const DEFAULT_OCR_ZONE_LANGUAGE = 'eng'

/** The field a zone writes to, keyed by OcrTemplate.combine_formats. */
export function getZoneFieldKey(zone: OcrTemplateZone): string | null {
  if (zone.target !== OcrZoneTarget.CustomField) return zone.target
  return zone.custom_field === null ? null : String(zone.custom_field)
}

/** Custom field types zone OCR can write to. See models.py OCR_SUPPORTED_FIELD_TYPES. */
export const OCR_SUPPORTED_FIELD_TYPES: CustomFieldDataType[] = [
  CustomFieldDataType.String,
  CustomFieldDataType.Url,
  CustomFieldDataType.Date,
  CustomFieldDataType.Integer,
  CustomFieldDataType.Float,
  CustomFieldDataType.Monetary,
  CustomFieldDataType.LongText,
  CustomFieldDataType.Boolean,
]

export const OCR_BUILTIN_TARGETS = [
  { id: OcrZoneTarget.Title, name: $localize`Title` },
  { id: OcrZoneTarget.Asn, name: $localize`Archive serial number` },
  { id: OcrZoneTarget.Created, name: $localize`Date created` },
]

export interface OcrTemplateZone {
  id?: number
  name: string
  target: OcrZoneTarget
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

export interface OcrTemplate extends MatchingModel, ObjectWithPermissions {
  name: string
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
  value: string | number | boolean | null
  reason?: string | null
}

export interface OcrZoneRunResponse {
  status: 'completed' | 'skipped'
  reason?: 'no_template'
  results: OcrZoneRunResult[]
}
