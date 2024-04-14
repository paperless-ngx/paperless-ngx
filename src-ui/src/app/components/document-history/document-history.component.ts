import { Component, Input, OnInit } from '@angular/core'
import { AuditLogAction, AuditLogEntry } from 'src/app/data/auditlog-entry'
import { DocumentService } from 'src/app/services/rest/document.service'

@Component({
  selector: 'pngx-document-history',
  templateUrl: './document-history.component.html',
  styleUrl: './document-history.component.scss',
})
export class DocumentHistoryComponent implements OnInit {
  public AuditLogAction = AuditLogAction

  private _documentId: number
  @Input()
  set documentId(id: number) {
    this._documentId = id
    this.ngOnInit()
  }

  public loading: boolean = true
  public entries: AuditLogEntry[] = []

  constructor(private documentService: DocumentService) {}

  ngOnInit(): void {
    if (this._documentId) {
      this.loading = true
      this.documentService
        .getHistory(this._documentId)
        .subscribe((auditLogEntries) => {
          this.entries = auditLogEntries
          this.loading = false
        })
    }
  }
}
