export interface WebsocketProgressMessage {
  filename?: string
  task_id?: string
  current_progress?: number
  max_progress?: number
  status?: string
  message?: string
  document_id: number
  owner_id?: number
  users_can_view?: number[]
  groups_can_view?: number[]
}
