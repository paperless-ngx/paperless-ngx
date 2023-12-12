import { Component, Input } from '@angular/core'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-preview-popup',
  templateUrl: './preview-popup.component.html',
  styleUrls: ['./preview-popup.component.scss'],
})
export class PreviewPopupComponent {
  @Input()
  document: PaperlessDocument

  error = false

  requiresPassword: boolean = false

  get renderAsObject(): boolean {
    return (this.isPdf && this.useNativePdfViewer) || !this.isPdf
  }

  get previewURL() {
    return this.documentService.getPreviewUrl(this.document.id)
  }

  get useNativePdfViewer(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER)
  }

  get isPdf(): boolean {
    // We dont have time to retrieve metadata, make a best guess by file name
    return (
      this.document?.original_file_name?.endsWith('.pdf') ||
      this.document?.archived_file_name?.endsWith('.pdf')
    )
  }

  constructor(
    private settingsService: SettingsService,
    private documentService: DocumentService
  ) {}

  onError(event: any) {
    if (event.name == 'PasswordException') {
      this.requiresPassword = true
    } else {
      this.error = true
    }
  }
}
