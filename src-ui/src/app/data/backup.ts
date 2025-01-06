import { Correspondent } from './correspondent'
import { Tag } from './tag'
import { DocumentType } from './document-type'
import { ArchiveFont } from './archive-font'
import { Observable } from 'rxjs'
import { StoragePath } from './storage-path'
import { Warehouse } from './warehouse'
import { ObjectWithPermissions } from './object-with-permissions'
import { DocumentNote } from './document-note'
import { CustomFieldInstance } from './custom-field-instance'
import { DocumentApproval } from './document-approval'


export interface Backup extends ObjectWithPermissions {
  [x: string]: any

  filename: string;
  created_at: string; // ISO 8601 string
  restore_at: string | null; // ISO 8601 string hoặc null
  restore_status: number;
  backup_status: number;
  detail: any | null; // JSON field
  log: string;
  count: number;
}
