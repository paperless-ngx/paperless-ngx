import { ObjectWithPermissions } from './object-with-permissions'

export enum ExportTargetKind {
  S3 = 's3',
  SFTP = 'sftp',
  Local = 'local',
}

export const EXPORT_TARGET_KINDS = [
  { id: ExportTargetKind.S3, name: $localize`S3`, icon: 'cloud-fill' },
  { id: ExportTargetKind.SFTP, name: $localize`SFTP`, icon: 'hdd-stack' },
  { id: ExportTargetKind.Local, name: $localize`Local`, icon: 'folder' },
]

export interface ExportTargetConfig {
  // S3
  bucket?: string

  prefix?: string

  endpoint?: string

  region?: string

  storage_class?: string

  // SFTP
  host?: string

  port?: number

  host_key?: string

  // SFTP & local
  path?: string
}

export interface ExportTarget extends ObjectWithPermissions {
  name: string

  kind: ExportTargetKind

  config: ExportTargetConfig

  access_key?: string

  secret_key?: string

  private_key?: string

  passphrase?: string

  retention_days?: number

  enabled: boolean
}
