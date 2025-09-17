import { ObjectWithId } from './object-with-id'

export interface ProcessedMail extends ObjectWithId {
  rule: number // MailRule.id
  folder: string
  uid: number
  subject: string
  received: Date
  processed: Date
  status: string
  error: string
}
