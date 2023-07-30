import { ObjectWithId } from './object-with-id'

export interface PaperlessIndexFieldMetadataDataItem {
  id: number
  name: string
  value: string
  displayName: string
}

export interface PaperlessIndexFieldMetadata extends ObjectWithId {
  created?: Date
  data?: PaperlessIndexFieldMetadataDataItem[]
  document: number
  user?: number // PaperlessUser
}
