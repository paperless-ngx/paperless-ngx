import {
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import { Document } from 'src/app/data/document'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { DocumentApproval } from 'src/app/data/document-approval'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { ApprovalEditDialogComponent } from '../../common/edit-dialog/approval-edit-dialog/approval-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { Subject, takeUntil } from 'rxjs'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: ['./document-card-large.component.scss'],
})
export class DocumentCardLargeComponent extends ComponentWithPermissions {
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
  selected = false

  @Output()
  toggleSelected = new EventEmitter()

  get selectable() {
    return this.toggleSelected.observers.length > 0
  }
  @Input()
  documentApproval: DocumentApproval
  @Input()
  document: Document

  @Output()
  dblClickDocument = new EventEmitter()

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  @Output()
  clickWarehouse = new EventEmitter<number>()

  @Output()
  clickDocumentType = new EventEmitter<number>()

  @Output()
  clickStoragePath = new EventEmitter<number>()

  @Output()
  clickMoreLike = new EventEmitter()

  @ViewChild('popover') popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  get searchScoreClass() {
    if (this.document.__search_hit__) {
      if (this.document.__search_hit__.score > 0.7) {
        return 'success'
      } else if (this.document.__search_hit__.score > 0.3) {
        return 'warning'
      } else {
        return 'danger'
      }
    }
  }

  get searchNoteHighlights() {
    let highlights = []
    if (
      this.document['__search_hit__'] &&
      this.document['__search_hit__'].note_highlights
    ) {
      // only show notes with a match
      highlights = (this.document['__search_hit__'].note_highlights as string)
        .split(',')
        .filter((highlight) => highlight.includes('<span'))
    }
    return highlights
  }

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

  mouseEnterPreview() {
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {
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

  get contentTrimmed() {
    return (
      this.document.content.substring(0, 500) +
      (this.document.content.length > 500 ? '...' : '')
    )
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
