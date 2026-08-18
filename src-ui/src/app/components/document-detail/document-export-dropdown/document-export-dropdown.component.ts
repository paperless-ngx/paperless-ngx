import { Clipboard } from '@angular/cdk/clipboard'
import {
  Component,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  inject,
  signal,
} from '@angular/core'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, first, takeUntil } from 'rxjs'
import { ExportRecord, ExportRecordStatus } from 'src/app/data/export-record'
import { ExportTarget } from 'src/app/data/export-target'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ExportTargetService } from 'src/app/services/rest/export-target.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-document-export-dropdown',
  templateUrl: './document-export-dropdown.component.html',
  styleUrls: ['./document-export-dropdown.component.scss'],
  imports: [NgbDropdownModule, NgxBootstrapIconsModule, CustomDatePipe],
})
export class DocumentExportDropdownComponent implements OnChanges, OnDestroy {
  ExportRecordStatus = ExportRecordStatus

  @Input() documentId: number

  readonly records = signal<ExportRecord[]>([])
  readonly loading = signal(false)
  readonly targets = signal<ExportTarget[]>([])
  readonly exporting = signal(false)
  readonly copiedRecordId = signal<number | null>(null)
  readonly retryingRecordId = signal<number | null>(null)

  private targetsLoaded = false

  private readonly documentService = inject(DocumentService)
  private readonly exportTargetService = inject(ExportTargetService)
  private readonly toastService = inject(ToastService)
  private readonly clipboard = inject(Clipboard)
  private readonly permissionsService = inject(PermissionsService)
  private readonly unsubscribeNotifier = new Subject<void>()

  ngOnChanges(changes: SimpleChanges): void {
    if (changes.documentId && this.documentId) {
      this.loadRecords()
    }
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  get canExportNow(): boolean {
    // Mirrors the API: delivering on demand needs a target to deliver to and
    // the right to record the delivery.
    return (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.ExportTarget
      ) &&
      this.permissionsService.currentUserCan(
        PermissionAction.Add,
        PermissionType.ExportRecord
      )
    )
  }

  loadRecords(): void {
    this.loading.set(true)
    this.documentService
      .getExports(this.documentId)
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (records) => {
          this.records.set(records)
          this.loading.set(false)
        },
        error: () => {
          this.loading.set(false)
        },
      })
  }

  onOpenChange(open: boolean): void {
    if (open && this.canExportNow && !this.targetsLoaded) {
      this.targetsLoaded = true
      this.exportTargetService
        .listAll()
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe({
          next: (r) => {
            this.targets.set(r.results.filter((target) => target.enabled))
          },
          error: () => {
            this.targetsLoaded = false
          },
        })
    }
  }

  exportNow(target: ExportTarget): void {
    this.exporting.set(true)
    this.documentService
      .exportNow(this.documentId, target.id)
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (record) => {
          this.exporting.set(false)
          this.toastService.showInfo(
            $localize`Export to "${target.name}" queued`
          )
          this.records.set([record, ...this.records()])
        },
        error: (e) => {
          this.exporting.set(false)
          this.toastService.showError(
            $localize`Error exporting to "${target.name}"`,
            e
          )
        },
      })
  }

  retry(record: ExportRecord): void {
    this.retryingRecordId.set(record.id)
    this.documentService
      .retryExport(this.documentId, record.id)
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (updated) => {
          this.retryingRecordId.set(null)
          this.toastService.showInfo(
            $localize`Export to "${updated.target_name}" queued`
          )
          this.records.set(
            this.records().map((r) => (r.id === updated.id ? updated : r))
          )
        },
        error: (e) => {
          this.retryingRecordId.set(null)
          this.toastService.showError($localize`Error retrying export`, e)
        },
      })
  }

  copyObjectKey(record: ExportRecord): void {
    this.clipboard.copy(record.object_key)
    this.copiedRecordId.set(record.id)
    setTimeout(() => {
      if (this.copiedRecordId() === record.id) {
        this.copiedRecordId.set(null)
      }
    }, 3000)
  }
}
