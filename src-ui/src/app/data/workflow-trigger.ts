import { ObjectWithId } from './object-with-id'

export enum DocumentSource {
  ConsumeFolder = 1,
  ApiUpload = 2,
  MailFetch = 3,
}

export enum WorkflowTriggerType {
  Consumption = 1,
  DocumentAdded = 2,
  DocumentUpdated = 3,
  ApprovalAdded = 4,
  ApprovalUpdated = 5,

}

export enum WorkflowTriggerStatus {
  Pending = "PENDING",
  Success = "SUCCESS",
  Revoked = "REVOKED",
  Failure = "FAILURE",
}

export enum WorkflowTriggerAccessType {
  Edit = "EDIT",
  View = "VIEW",
  Owner = "OWNER",
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

  filter_has_correspondent?: number // Correspondent.id

  filter_has_document_type?: number // DocumentType.id

  filter_has_groups?: number[] // Group.id[]

  filter_has_status?: WorkflowTriggerStatus

  filter_has_access_type?: WorkflowTriggerAccessType

  filter_has_content_type?: number
}
