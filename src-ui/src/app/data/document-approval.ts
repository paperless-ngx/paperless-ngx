import { Group } from './group'
import { ObjectWithId } from './object-with-id'
import { User } from './user'

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

export interface DocumentApproval extends ObjectWithId {
  
  access_type: PaperlessApprovalAccessType

  status: PaperlessApprovalStatus

  submitted_by: number

  object_pk: string

  created: Date

  modified?: Date

  expiration?: Date

  ctype?: number

  submitted_by_group?: number[]

  name?: string
}
