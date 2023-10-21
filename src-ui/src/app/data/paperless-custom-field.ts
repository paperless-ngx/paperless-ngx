import { ObjectWithId } from './object-with-id'

export enum PaperlessCustomFieldDataType {
  String = 'string',
  Url = 'url',
  Date = 'date',
}

export interface PaperlessCustomField extends ObjectWithId {
  type: PaperlessCustomFieldDataType
  name: string
  data: any
  document: number // PaperlessDocument
  created?: Date
  user: number // PaperlessUser
}
