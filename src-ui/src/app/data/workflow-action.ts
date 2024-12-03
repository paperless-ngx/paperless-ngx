import { ObjectWithId } from './object-with-id'

export enum WorkflowActionType {
  Assignment = 1,
  Removal = 2,
  Email = 3,
  Webhook = 4,
}

export interface WorkflowActionEmail extends ObjectWithId {
  subject?: string

  body?: string

  to?: string

  include_document?: boolean
}

export interface WorkflowActionWebhook extends ObjectWithId {
  url?: string

  use_params?: boolean

  params?: object

  body?: string

  headers?: object

  include_document?: boolean
}

export interface WorkflowAction extends ObjectWithId {
  type: WorkflowActionType

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

  remove_tags?: number[] // Tag.id

  remove_all_tags?: boolean

  remove_document_types?: number[] // [DocumentType.id]

  remove_all_document_types?: boolean

  remove_correspondents?: number[] // [Correspondent.id]

  remove_all_correspondents?: boolean

  remove_storage_paths?: number[] // [StoragePath.id]

  remove_all_storage_paths?: boolean

  remove_owners?: number[] // [User.id]

  remove_all_owners?: boolean

  remove_view_users?: number[] // [User.id]

  remove_view_groups?: number[] // [Group.id]

  remove_change_users?: number[] // [User.id]

  remove_change_groups?: number[] // [Group.id]

  remove_all_permissions?: boolean

  remove_custom_fields?: number[] // [CustomField.id]

  remove_all_custom_fields?: boolean

  email?: WorkflowActionEmail

  webhook?: WorkflowActionWebhook
}
