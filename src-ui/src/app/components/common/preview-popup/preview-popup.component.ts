import { Component, Input } from '@angular/core'

@Component({
  selector: 'pngx-preview-popup',
  templateUrl: './preview-popup.component.html',
  styleUrls: ['./preview-popup.component.scss'],
})
export class PreviewPopupComponent {
  @Input()
  renderAsPlainText: boolean = false

  @Input()
  previewText: string

  @Input()
  previewURL: string

  @Input()
  useNativePdfViewer: boolean = false

  error = false
  requiresPassword: boolean = false

  onError(event) {
    if (event.name == 'PasswordException') {
      this.requiresPassword = true
    } else {
      this.error = true
    }
  }
}
