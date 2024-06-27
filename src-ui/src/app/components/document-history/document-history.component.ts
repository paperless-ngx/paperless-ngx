import { Component, Input, OnInit } from '@angular/core'
import { Observable, first, map, of } from 'rxjs'
import { AuditLogAction, AuditLogEntry } from 'src/app/data/auditlog-entry'
import { DataType } from 'src/app/data/datatype'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'

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

  constructor(
    private documentService: DocumentService,
    private correspondentService: CorrespondentService,
    private storagePathService: StoragePathService,
    private documentTypeService: DocumentTypeService,
    private userService: UserService
  ) {}

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

  getPrettyName(type: DataType | string, id: string): Observable<string> {
    switch (type) {
      case DataType.Correspondent:
        return this.correspondentService.getCached(parseInt(id, 10)).pipe(
          first(),
          map((correspondent) => correspondent?.name ?? id)
        )
      case DataType.DocumentType:
        return this.documentTypeService.getCached(parseInt(id, 10)).pipe(
          first(),
          map((documentType) => documentType?.name ?? id)
        )
      case DataType.StoragePath:
        return this.storagePathService.getCached(parseInt(id, 10)).pipe(
          first(),
          map((storagePath) => storagePath?.path ?? id)
        )
      case 'owner':
        return this.userService.getCached(parseInt(id, 10)).pipe(
          first(),
          map((user) => user?.username ?? id)
        )
      default:
        return of(id)
    }
  }
}
