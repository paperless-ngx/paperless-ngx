import { ObjectWithId } from './object-with-id'

export enum DocumentSource {
  ConsumeFolder = 1,
  ApiUpload = 2,
  MailFetch = 3,
}

export interface PaperlessConsumptionTemplate extends ObjectWithId {
  name: string

  order: number

  sources: DocumentSource[]

  filter_filename: string

  filter_path?: string

  filter_mailrule?: number // PaperlessMailRule.id

  assign_title?: string

  assign_tags?: number[] // PaperlessTag.id

  assign_document_type?: number // PaperlessDocumentType.id

  assign_correspondent?: number // PaperlessCorrespondent.id

  assign_storage_path?: number // PaperlessStoragePath.id

  assign_owner?: number // PaperlessUser.id

  assign_view_users?: number[] // [PaperlessUser.id]

  assign_view_groups?: number[] // [PaperlessGroup.id]

  assign_change_users?: number[] // [PaperlessUser.id]

  assign_change_groups?: number[] // [PaperlessGroup.id]
}
