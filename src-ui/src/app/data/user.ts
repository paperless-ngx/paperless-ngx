import { ObjectWithId } from './object-with-id'

export interface User extends ObjectWithId {
  username?: string
  first_name?: string
  last_name?: string
  date_joined?: Date
  is_staff?: boolean
  is_active?: boolean
  is_superuser?: boolean
  groups?: number[] // Group[]
  user_permissions?: string[]
  inherited_permissions?: string[]
  is_mfa_enabled?: boolean
}
