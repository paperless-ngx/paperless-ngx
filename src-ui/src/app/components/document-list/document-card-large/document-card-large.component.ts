import { Component, EventEmitter, Input, OnInit, Output, ViewChild } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { DocumentService } from 'src/app/services/rest/document.service';
import { SettingsService, SETTINGS_KEYS } from 'src/app/services/settings.service';
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: ['./document-card-large.component.scss', '../popover-preview/popover-preview.scss']
})
export class DocumentCardLargeComponent implements OnInit {

  constructor(private documentService: DocumentService, private sanitizer: DomSanitizer, private settingsService: SettingsService) { }

  @Input()
  selected = false

  @Output()
  toggleSelected = new EventEmitter()

  get selectable() {
    return this.toggleSelected.observers.length > 0
  }

  @Input()
  moreLikeThis: boolean = false

  @Input()
  document: PaperlessDocument

  @Input()
  details: any

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  @Output()
  clickDocumentType = new EventEmitter<number>()

  @Input()
  searchScore: number

  @ViewChild('popover') popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  get searchScoreClass() {
    if (this.searchScore > 0.7) {
      return "success"
    } else if (this.searchScore > 0.3) {
      return "warning"
    } else {
      return "danger"
    }
  }

  ngOnInit(): void {
  }

  getIsThumbInverted() {
    return this.settingsService.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)
  }

  getDetailsAsString() {
    if (typeof this.details === 'string') {
      return this.details.substring(0, 500)
    }
  }

  getDetailsAsHighlight() {
    //TODO: this is not an exact typecheck, can we do better
    if (this.details instanceof Array) {
      return this.details
    }
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
      }, 600);
    }
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
  }

  mouseLeaveCard() {
    this.popover.close()
  }
}
