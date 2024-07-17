import {
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import { map } from 'rxjs/operators'
import { Subject, takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { ApprovalEditDialogComponent } from '../../common/edit-dialog/approval-edit-dialog/approval-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentApproval } from 'src/app/data/document-approval'
import { ApprovalsComponent } from '../../admin/approval/approvals.component'

@Component({
  selector: 'pngx-document-card-small',
  templateUrl: './document-card-small.component.html',
  styleUrls: ['./document-card-small.component.scss'],
})
export class DocumentCardSmallComponent extends ComponentWithPermissions {
  private unsubscribeNotifier: Subject<any> = new Subject()
  constructor(
    private documentService: DocumentService,
    public settingsService: SettingsService,
    private modalService: NgbModal,
    private toastService: ToastService
  ) {
    super()
  }

  @Input()
  documentApproval: DocumentApproval

  @Input()
  selected = false

  @Output()
  toggleSelected = new EventEmitter()

  @Input()
  document: Document

  @Output()
  dblClickDocument = new EventEmitter()

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  @Output()
  clickDocumentType = new EventEmitter<number>()

  @Output()
  clickStoragePath = new EventEmitter<number>()

  @Output()
  clickWarehouse = new EventEmitter<number>()

  moreTags: number = null

  @ViewChild('popover') popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  getIsThumbInverted() {
    return this.settingsService.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document.id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document.id)
  }

  get previewUrl() {
    return this.documentService.getPreviewUrl(this.document.id)
  }

  get privateName() {
    return $localize`Private`
  }

  getTagsLimited$() {
    const limit = this.document.notes.length > 0 ? 6 : 7
    return this.document.tags$?.pipe(
      map((tags) => {
        if (tags.length > limit) {
          this.moreTags = tags.length - (limit - 1)
          return tags.slice(0, limit - 1)
        } else {
          return tags
        }
      })
    )
  }

  mouseEnterPreview() {
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {
      // we're going to open but hide to pre-load content during hover delay
      this.popover.open()
      this.popoverHidden = true
      setTimeout(() => {
        if (this.mouseOnPreview) {
          // show popover
          this.popoverHidden = false
        } else {
          this.popover.close()
        }
      }, 600)
    }
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
  }

  mouseLeaveCard() {
    this.popover.close()
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }

  editField() {
    this.documentApproval = {
      id: undefined,
      access_type: null,
      status: undefined,
      submitted_by: null,
      object_pk: this.document.id.toString(),
      created: undefined,
      modified: undefined,
      expiration: null,
      ctype: 14,
      submitted_by_group: [],
      name: undefined,
    }

    const modal = this.modalService.open(ApprovalEditDialogComponent)
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = this.documentApproval
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newField) => {
        this.toastService.showInfo($localize`Successfully sent mining request to "${newField.name}".`)
        // this.documentService.clearCache()
        // this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving fieldSubmitted mining request failed.`, e)
      })
  }
}
