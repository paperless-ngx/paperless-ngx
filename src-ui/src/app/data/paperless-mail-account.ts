import { ObjectWithId } from './object-with-id'

export enum IMAPSecurity {
  None = 0,
  SSL = 1,
  STARTTLS = 2,
}

export interface PaperlessMailAccount extends ObjectWithId {
  name: string

  imap_server: string

  imap_port: number

  imap_security: IMAPSecurity

  username: string

  password: string

  character_set?: string
}
