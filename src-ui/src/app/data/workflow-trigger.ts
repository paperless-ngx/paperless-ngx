import { ObjectWithId } from './object-with-id'

export enum DocumentSource {
  ConsumeFolder = 1,
  ApiUpload = 2,
  MailFetch = 3,
  WebUI = 4,
}

export enum WorkflowTriggerType {
  Consumption = 1,
  DocumentAdded = 2,
  DocumentUpdated = 3,
  Scheduled = 4,
}

export enum ScheduleDateField {
  Added = 'added',
  Created = 'created',
  Modified = 'modified',
  CustomField = 'custom_field',
}

export interface WorkflowTrigger extends ObjectWithId {
  type: WorkflowTriggerType

  sources?: DocumentSource[]

  filter_filename?: string

  filter_path?: string

  filter_mailrule?: number // MailRule.id

  match?: string

  matching_algorithm?: number

  is_insensitive?: boolean

  filter_has_tags?: number[] // Tag.id[]

  filter_has_all_tags?: number[] // Tag.id[]

  filter_has_not_tags?: number[] // Tag.id[]

  filter_has_any_correspondents?: number[] // Correspondent.id[]

  filter_has_not_correspondents?: number[] // Correspondent.id[]

  filter_has_any_document_types?: number[] // DocumentType.id[]

  filter_has_not_document_types?: number[] // DocumentType.id[]

  filter_has_any_storage_paths?: number[] // StoragePath.id[]

  filter_has_not_storage_paths?: number[] // StoragePath.id[]

  filter_custom_field_query?: string

  filter_has_correspondent?: number // Correspondent.id

  filter_has_document_type?: number // DocumentType.id

  filter_has_storage_path?: number // StoragePath.id

  schedule_offset_days?: number

  schedule_is_recurring?: boolean

  schedule_recurring_interval_days?: number

  schedule_date_field?: ScheduleDateField

  schedule_date_custom_field?: number // CustomField.id
}
