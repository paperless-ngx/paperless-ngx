import { ObjectWithId } from './object-with-id'
import { WorkflowAction } from './workflow-action'
import { WorkflowTrigger } from './workflow-trigger'

export interface Workflow extends ObjectWithId {
  name: string

  order: number

  enabled: boolean

  triggers: WorkflowTrigger[]

  actions: WorkflowAction[]
}
