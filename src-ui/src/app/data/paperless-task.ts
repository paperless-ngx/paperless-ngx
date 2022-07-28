import { ObjectWithId } from './object-with-id'

export enum PaperlessTaskType {
  // just file tasks, for now
  File = 'file',
}

export enum PaperlessTaskStatus {
  Queued = 'queued',
  Started = 'started',
  Complete = 'complete',
  Failed = 'failed',
  Unknown = 'unknown',
}

export interface PaperlessTask extends ObjectWithId {
  type: PaperlessTaskType

  status: PaperlessTaskStatus

  acknowledged: boolean

  task_id: string

  name: string

  created: Date

  started?: Date

  result: string
}
