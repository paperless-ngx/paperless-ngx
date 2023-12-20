import { ObjectWithId } from './object-with-id'

export enum DocumentSource {
  ConsumeFolder = 1,
  ApiUpload = 2,
  MailFetch = 3,
}

export interface ConsumptionTemplate extends ObjectWithId {
  name: string

  order: number

  sources: DocumentSource[]

  filter_filename: string

  filter_path?: string

  filter_mailrule?: number // MailRule.id

  assign_title?: string

  assign_tags?: number[] // Tag.id

  assign_document_type?: number // DocumentType.id

  assign_correspondent?: number // Correspondent.id

  assign_storage_path?: number // StoragePath.id

  assign_owner?: number // User.id

  assign_view_users?: number[] // [User.id]

  assign_view_groups?: number[] // [Group.id]

  assign_change_users?: number[] // [User.id]

  assign_change_groups?: number[] // [Group.id]

  assign_custom_fields?: number[] // [CustomField.id]
}
