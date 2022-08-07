import { ObjectWithId } from './object-with-id'
import { CommentUser } from './user-type'

export interface PaperlessDocumentComment extends ObjectWithId {
    created?: Date
    comment?: string
    user?: CommentUser
} 