import {
  Component,
  EventEmitter,
  Input,
  OnInit,
  Output,
  ViewChild,
} from '@angular/core'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_FULLTEXT_MORELIKE } from 'src/app/data/filter-rule-type'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'

@Component({
  selector: 'app-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: [
    './document-card-large.component.scss',
    '../popover-preview/popover-preview.scss',
  ],
})
export class DocumentCardLargeComponent implements OnInit {
  constructor(
    private documentService: DocumentService,
    private settingsService: SettingsService,
    public openDocumentsService: OpenDocumentsService
  ) {}

  @Input()
  selected = false

  @Output()
  toggleSelected = new EventEmitter()

  get selectable() {
    return this.toggleSelected.observers.length > 0
  }

  @Input()
  document: PaperlessDocument

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

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

  ngOnInit(): void {}

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

  get contentTrimmed() {
    return this.document.content.substr(0, 500)
  }
}
