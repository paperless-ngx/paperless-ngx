import { ObjectWithId } from './object-with-id'

export enum WorkflowActionType {
  Assignment = 1,
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
}
