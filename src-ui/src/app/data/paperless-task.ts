import { ObjectWithId } from './object-with-id'

export enum PaperlessTaskType {
  ConsumeFile = 'consume_file',
  TrainClassifier = 'train_classifier',
  SanityCheck = 'sanity_check',
  MailFetch = 'mail_fetch',
  LlmIndex = 'llm_index',
  EmptyTrash = 'empty_trash',
  CheckWorkflows = 'check_workflows',
  BulkUpdate = 'bulk_update',
  ReprocessDocument = 'reprocess_document',
  BuildShareLink = 'build_share_link',
  BulkDelete = 'bulk_delete',
}

export enum PaperlessTaskTypeFilter {
  All = 'all',
  ConsumeFile = PaperlessTaskType.ConsumeFile,
  TrainClassifier = PaperlessTaskType.TrainClassifier,
  SanityCheck = PaperlessTaskType.SanityCheck,
  MailFetch = PaperlessTaskType.MailFetch,
  LlmIndex = PaperlessTaskType.LlmIndex,
  EmptyTrash = PaperlessTaskType.EmptyTrash,
  CheckWorkflows = PaperlessTaskType.CheckWorkflows,
  BulkUpdate = PaperlessTaskType.BulkUpdate,
  ReprocessDocument = PaperlessTaskType.ReprocessDocument,
  BuildShareLink = PaperlessTaskType.BuildShareLink,
  BulkDelete = PaperlessTaskType.BulkDelete,
}

export enum PaperlessTaskTriggerSource {
  Scheduled = 'scheduled',
  WebUI = 'web_ui',
  ApiUpload = 'api_upload',
  FolderConsume = 'folder_consume',
  EmailConsume = 'email_consume',
  System = 'system',
  Manual = 'manual',
}

export enum PaperlessTaskTriggerSourceFilter {
  All = 'all',
  Scheduled = PaperlessTaskTriggerSource.Scheduled,
  WebUI = PaperlessTaskTriggerSource.WebUI,
  ApiUpload = PaperlessTaskTriggerSource.ApiUpload,
  FolderConsume = PaperlessTaskTriggerSource.FolderConsume,
  EmailConsume = PaperlessTaskTriggerSource.EmailConsume,
  System = PaperlessTaskTriggerSource.System,
  Manual = PaperlessTaskTriggerSource.Manual,
}

export enum PaperlessTaskStatus {
  Pending = 'pending',
  Started = 'started',
  Success = 'success',
  Failure = 'failure',
  Revoked = 'revoked',
}

export interface PaperlessTask extends ObjectWithId {
  task_id: string
  task_type: PaperlessTaskType
  task_type_display: string
  trigger_source: PaperlessTaskTriggerSource
  trigger_source_display: string
  status: PaperlessTaskStatus
  status_display: string
  date_created: Date
  date_started?: Date
  date_done?: Date
  duration_seconds?: number
  wait_time_seconds?: number
  input_data: Record<string, any>
  result_data?: Record<string, any>
  related_document_ids: number[]
  acknowledged: boolean
  owner?: number
}

export interface PaperlessTaskSummary {
  task_type: PaperlessTaskType
  total_count: number
  pending_count: number
  success_count: number
  failure_count: number
  avg_duration_seconds: number | null
  avg_wait_time_seconds: number | null
  last_run: Date | null
  last_success: Date | null
  last_failure: Date | null
}
