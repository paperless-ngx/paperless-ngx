import { ObjectWithPermissions } from './object-with-permissions'

export enum IMAPSecurity {
  None = 1,
  SSL = 2,
  STARTTLS = 3,
}

export enum MailAccountType {
  IMAP = 1,
  Gmail_OAuth = 2,
  Outlook_OAuth = 3,
}

export interface MailAccount extends ObjectWithPermissions {
  name: string

  imap_server: string

  imap_port: number

  imap_security: IMAPSecurity

  username: string

  password: string

  character_set?: string

  is_token: boolean

  account_type: MailAccountType

  expiration?: string // Date
}
