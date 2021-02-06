import { Component, EventEmitter, Input, OnInit, Output, ViewChild } from '@angular/core';
import { map } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessDocumentMetadata } from 'src/app/data/paperless-document-metadata';
import { DocumentService } from 'src/app/services/rest/document.service';
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap';
import { SettingsService, SETTINGS_KEYS } from 'src/app/services/settings.service';

@Component({
  selector: 'app-document-card-small',
  templateUrl: './document-card-small.component.html',
  styleUrls: ['./document-card-small.component.scss']
})
export class DocumentCardSmallComponent implements OnInit {

  constructor(private documentService: DocumentService, private settings: SettingsService) { }

  @Input()
  selected = false

  @Output()
  toggleSelected = new EventEmitter()

  @Input()
  document: PaperlessDocument

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  moreTags: number = null

  @Output()
  showPreview = new EventEmitter<DocumentCardSmallComponent>()

  @ViewChild('popover') popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  metadata: PaperlessDocumentMetadata

  ngOnInit(): void {
    this.documentService.getMetadata(this.document?.id).subscribe(result => {
      this.metadata = result
    })
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

  getTagsLimited$() {
    return this.document.tags$.pipe(
      map(tags => {
        if (tags.length > 7) {
          this.moreTags = tags.length - 6
          return tags.slice(0, 6)
        } else {
          return tags
        }
      })
    )
  }

  get useNativePdfViewer(): boolean {
    return this.settings.get(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER)
  }

  getContentType() {
    return this.metadata?.has_archive_version ? 'application/pdf' : this.metadata?.original_mime_type
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
          this.showPreview.emit(this)
        } else {
          this.popover.close()
        }
      }, 600);
    }
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
  }
}
