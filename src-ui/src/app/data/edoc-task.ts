import { ObjectWithId } from './object-with-id'

export enum EdocTaskType {
  // just file tasks, for now
  File = 'file',
}

export enum EdocTaskStatus {
  Pending = 'PENDING',
  Started = 'STARTED',
  Complete = 'SUCCESS',
  Failed = 'FAILURE',
}

export interface EdocTask extends ObjectWithId {
  type: EdocTaskType

  status: EdocTaskStatus

  acknowledged: boolean

  task_id: string

  task_file_name: string

  date_created: Date

  date_done?: Date

  result?: string

  related_document?: number
}
