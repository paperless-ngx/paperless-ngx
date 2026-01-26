export enum InstallType {
  Containerized = 'containerized',
  BareMetal = 'bare-metal',
}

export enum SystemStatusItemStatus {
  OK = 'OK',
  ERROR = 'ERROR',
  WARNING = 'WARNING',
  DISABLED = 'DISABLED',
}

export interface SystemStatus {
  pngx_version: string
  server_os: string
  install_type: InstallType
  storage: {
    total: number
    available: number
  }
  database: {
    type: string
    url: string
    status: SystemStatusItemStatus
    error?: string
    migration_status: {
      latest_migration: string
      unapplied_migrations: string[]
    }
  }
  tasks: {
    redis_url: string
    redis_status: SystemStatusItemStatus
    redis_error: string
    celery_status: SystemStatusItemStatus
    celery_url: string
    celery_error: string
    index_status: SystemStatusItemStatus
    index_last_modified: string // ISO date string
    index_error: string
    classifier_status: SystemStatusItemStatus
    classifier_last_trained: string // ISO date string
    classifier_error: string
    sanity_check_status: SystemStatusItemStatus
    sanity_check_last_run: string // ISO date string
    sanity_check_error: string
    llmindex_status: SystemStatusItemStatus
    llmindex_last_modified: string // ISO date string
    llmindex_error: string
  }
  websocket_connected?: SystemStatusItemStatus // added client-side
}
