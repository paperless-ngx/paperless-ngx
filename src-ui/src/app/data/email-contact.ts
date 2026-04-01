import { ObjectWithId } from './object-with-id'

export interface EmailContact extends ObjectWithId {
  name?: string
  email?: string
  owner?: number
}
