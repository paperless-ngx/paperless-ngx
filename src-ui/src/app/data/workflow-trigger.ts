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
}

export interface WorkflowTrigger extends ObjectWithId {
  type: WorkflowTriggerType

  sources?: DocumentSource[]

  filter_filename?: string

  filter_path?: string

  filter_mailrule?: number // MailRule.id
}
