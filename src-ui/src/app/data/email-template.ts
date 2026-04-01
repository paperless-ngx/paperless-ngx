import { ObjectWithId } from './object-with-id'

export interface EmailTemplate extends ObjectWithId {
  name?: string
  subject?: string
  body?: string
  owner?: number
}
