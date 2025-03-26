import { ObjectWithId } from './object-with-id'

export enum ApprovalAccessType {
  // just file tasks, for now
  Owner = 'OWNER',
  Edit = 'EDIT',
  View = 'VIEW',

}

export enum ApprovalStatus {
  Pending = 'PENDING',
  Success = 'SUCCESS',
  Failure = 'FAILURE',
  Revoked = 'REVOKED',
}

export interface Approval extends ObjectWithId {

  access_type: ApprovalAccessType

  access_type_display?: string

  status: ApprovalStatus

  submitted_by: number

  object_pk: string

  task_file_name: string

  created: Date

  modified?: Date

  ctype?: string

  submitted_by_group?: number[]

  name?: string
}
