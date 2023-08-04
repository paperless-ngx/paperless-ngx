import { ObjectWithPermissions } from './object-with-permissions'

export enum IMAPSecurity {
  None = 1,
  SSL = 2,
  STARTTLS = 3,
}

export interface PaperlessMailAccount extends ObjectWithPermissions {
  name: string

  imap_server: string

  imap_port: number

  imap_security: IMAPSecurity

  username: string

  password: string

  character_set?: string

  is_token: boolean
}
