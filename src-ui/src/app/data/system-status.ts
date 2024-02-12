export enum PaperlessInstallType {
  Containerized = 'containerized',
  BareMetal = 'bare-metal',
}

export enum PaperlessConnectionStatus {
  OK = 'OK',
  ERROR = 'ERROR',
}

export interface PaperlessSystemStatus {
  pngx_version: string
  server_os: string
  install_type: PaperlessInstallType
  storage: {
    total: number
    available: number
  }
  database: {
    type: string
    url: string
    status: PaperlessConnectionStatus
    error?: string
    migration_status: {
      latest_migration: string
      unapplied_migrations: string[]
    }
  }
  tasks: {
    redis_url: string
    redis_status: PaperlessConnectionStatus
    redis_error: string
    celery_status: PaperlessConnectionStatus
  }
}
