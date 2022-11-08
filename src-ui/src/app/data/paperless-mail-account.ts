import { ObjectWithId } from './object-with-id'

export enum IMAPSecurity {
  None = 1,
  SSL = 2,
  STARTTLS = 3,
}

export const IMAPSecurityLabels: Array<{ id: number; name: string }> = [
  { id: IMAPSecurity.None, name: $localize`No encryption` },
  { id: IMAPSecurity.SSL, name: $localize`SSL` },
  { id: IMAPSecurity.STARTTLS, name: $localize`STARTTLS` },
]

export interface PaperlessMailAccount extends ObjectWithId {
  name: string

  imap_server: string

  imap_port: number

  imap_security: IMAPSecurity

  username: string

  password: string

  character_set?: string
}
