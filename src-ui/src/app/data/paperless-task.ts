import { ObjectWithId } from './object-with-id'

export enum PaperlessTaskType {
  // just file tasks, for now
  File = 'file',
}

export enum PaperlessTaskStatus {
  Pending = 'PENDING',
  Started = 'STARTED',
  Complete = 'SUCCESS',
  Failed = 'FAILURE',
}

export interface PaperlessTask extends ObjectWithId {
  type: PaperlessTaskType

  status: PaperlessTaskStatus

  acknowledged: boolean

  task_id: string

  name: string

  created: Date

  done?: Date

  result: string
}
