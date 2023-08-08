export interface WebsocketConsumerStatusMessage {
  filename?: string
  task_id?: string
  current_progress?: number
  max_progress?: number
  status?: string
  message?: string
  document_id: number
  owner_id?: number
}
