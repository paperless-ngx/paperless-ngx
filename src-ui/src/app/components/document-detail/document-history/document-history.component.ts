import { AsyncPipe, KeyValuePipe, TitleCasePipe } from '@angular/common'
import { Component, Input, OnInit, inject } from '@angular/core'
import { NgbTooltipModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Observable, first, map, of, shareReplay } from 'rxjs'
import { AuditLogAction, AuditLogEntry } from 'src/app/data/auditlog-entry'
import { DataType } from 'src/app/data/datatype'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'

@Component({
  selector: 'pngx-document-history',
  templateUrl: './document-history.component.html',
  styleUrl: './document-history.component.scss',
  imports: [
    CustomDatePipe,
    NgbTooltipModule,
    AsyncPipe,
    KeyValuePipe,
    TitleCasePipe,
    NgxBootstrapIconsModule,
  ],
})
export class DocumentHistoryComponent implements OnInit {
  private documentService = inject(DocumentService)
  private correspondentService = inject(CorrespondentService)
  private storagePathService = inject(StoragePathService)
  private documentTypeService = inject(DocumentTypeService)
  private userService = inject(UserService)

  public AuditLogAction = AuditLogAction

  private _documentId: number
  @Input()
  set documentId(id: number) {
    if (this._documentId !== id) {
      this._documentId = id
      this.prettyNameCache.clear()
      this.loadHistory()
    }
  }

  public loading: boolean = true
  public entries: AuditLogEntry[] = []

  private readonly prettyNameCache = new Map<string, Observable<string>>()

  ngOnInit(): void {
    this.loadHistory()
  }

  private loadHistory(): void {
    if (this._documentId) {
      this.loading = true
      this.documentService.getHistory(this._documentId).subscribe((entries) => {
        this.entries = entries
        this.loading = false
      })
    }
  }

  getPrettyName(type: DataType | string, id: string): Observable<string> {
    const cacheKey = `${type}:${id}`
    const cached = this.prettyNameCache.get(cacheKey)
    if (cached) {
      return cached
    }

    const idInt = parseInt(id, 10)
    const fallback$ = of(id)

    let result$: Observable<string>
    if (!Number.isFinite(idInt)) {
      result$ = fallback$
    } else {
      switch (type) {
        case DataType.Correspondent:
          result$ = this.correspondentService.getCached(idInt).pipe(
            first(),
            map((correspondent) => correspondent?.name ?? id)
          )
          break
        case DataType.DocumentType:
          result$ = this.documentTypeService.getCached(idInt).pipe(
            first(),
            map((documentType) => documentType?.name ?? id)
          )
          break
        case DataType.StoragePath:
          result$ = this.storagePathService.getCached(idInt).pipe(
            first(),
            map((storagePath) => storagePath?.path ?? id)
          )
          break
        case 'owner':
          result$ = this.userService.getCached(idInt).pipe(
            first(),
            map((user) => user?.username ?? id)
          )
          break
        default:
          result$ = fallback$
      }
    }

    const shared$ = result$.pipe(shareReplay({ bufferSize: 1, refCount: true }))
    this.prettyNameCache.set(cacheKey, shared$)
    return shared$
  }
}
