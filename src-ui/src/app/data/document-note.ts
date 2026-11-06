import { ObjectWithId } from './object-with-id'
import { User } from './user'

export enum NoteFormat {
  Plain = 'plain',
  Markdown = 'markdown',
}

export interface DocumentNote extends ObjectWithId {
  created?: Date
  note?: string
  user?: User
  format?: NoteFormat
}
