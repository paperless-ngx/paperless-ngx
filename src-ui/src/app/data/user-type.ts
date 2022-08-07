import { ObjectWithId } from './object-with-id'

export interface CommentUser extends ObjectWithId {
    username: string
    firstname: string
    lastname: string
} 