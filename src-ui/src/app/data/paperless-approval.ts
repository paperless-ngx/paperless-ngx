import { ObjectWithId } from './object-with-id'

export enum PaperlessApprovalAccessType {
  // just file tasks, for now
  Owner = 'OWNER',
  Edit = 'EDIT',
  View = 'VIEW',

}

export enum PaperlessApprovalStatus {
  Pending = 'PENDING',
  Success = 'SUCCESS',
  Failure = 'FAILURE',
  Revoked = 'REVOKED',
}

export interface PaperlessApproval extends ObjectWithId {

  access_type: PaperlessApprovalAccessType

  access_type_display?: string

  status: PaperlessApprovalStatus

  submitted_by: number

  object_pk: string

  task_file_name: string

  created: Date

  modified?: Date

  ctype?: string

  submitted_by_group?: number[]

  name?: string
}
