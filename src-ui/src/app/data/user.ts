import { ObjectWithId } from './object-with-id'

export interface User extends ObjectWithId {
  username: string
  firstname: string
  lastname: string
}
