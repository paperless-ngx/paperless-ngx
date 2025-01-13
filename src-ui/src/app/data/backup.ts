import { ObjectWithPermissions } from './object-with-permissions'


export interface Backup extends ObjectWithPermissions {
  [x: string]: any

  filename: string;
  created_at: string; // ISO 8601 string
  restore_at: string | null; // ISO 8601 string hoặc null
  restore_status: number;
  backup_status: number;
  detail: {
    documents?: number | 0
    size?: number | 0
  }
  log: string;
  is_backup?: boolean;
  is_restore?: boolean;
}
