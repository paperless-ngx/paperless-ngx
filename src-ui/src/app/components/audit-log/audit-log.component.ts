import { Component, Input, OnInit } from '@angular/core'
import { AuditLogEntry } from 'src/app/data/auditlog-entry'
import { DocumentService } from 'src/app/services/rest/document.service'

@Component({
  selector: 'pngx-audit-log',
  templateUrl: './audit-log.component.html',
  styleUrl: './audit-log.component.scss',
})
export class AuditLogComponent implements OnInit {
  _documentId: number
  @Input()
  set documentId(id: number) {
    this._documentId = id
    this.ngOnInit()
  }

  public loading: boolean = true
  public entries: AuditLogEntry[] = []
  public openEntries: Set<number> = new Set()

  constructor(private documentService: DocumentService) {}

  ngOnInit(): void {
    if (this._documentId) {
      this.loading = true
      this.documentService
        .getAuditLog(this._documentId)
        .subscribe((auditLogEntries) => {
          this.entries = auditLogEntries
          this.loading = false
        })
    }
  }

  toggleEntry(entry: AuditLogEntry) {
    if (this.openEntries.has(entry.id)) {
      this.openEntries.delete(entry.id)
    } else {
      this.openEntries.add(entry.id)
    }
  }
}
