import { User } from './user'

export enum AuditLogAction {
  Create = 'create',
  Update = 'update',
  Delete = 'delete',
}

export interface AuditLogEntry {
  id: number
  timestamp: string
  action: AuditLogAction
  changes: any
  remote_addr: string
  actor?: User
}
