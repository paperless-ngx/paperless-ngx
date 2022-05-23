import { ObjectWithId } from './object-with-id'

export interface PaperlessTask extends ObjectWithId {
  acknowledged: boolean

  q_task_id: string

  name: string

  created: Date

  result: string
}
