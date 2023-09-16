import { ObjectWithPermissions } from './object-with-permissions'

export interface PaperlessConsumptionTemplate extends ObjectWithPermissions {
  name: string

  order: number

  filter_filename: string

  filter_path: string

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
