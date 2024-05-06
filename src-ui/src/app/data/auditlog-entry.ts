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
  changes: {
    [key: string]: string[]
  }
  remote_addr: string
  actor?: User
}
