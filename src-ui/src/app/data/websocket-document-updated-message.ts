export interface WebsocketDocumentUpdatedMessage {
  document_id: number
  modified: string
  owner_id?: number
  users_can_view?: number[]
  groups_can_view?: number[]
}
