import { ObjectWithId } from './object-with-id'

export interface PaperlessTask extends ObjectWithId {
  acknowledged: boolean

  task_id: string

  name: string

  created: Date
}
