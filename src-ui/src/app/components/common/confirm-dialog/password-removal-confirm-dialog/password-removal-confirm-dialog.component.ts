import { Component, Input } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-password-removal-confirm-dialog',
  templateUrl: './password-removal-confirm-dialog.component.html',
  styleUrls: ['./password-removal-confirm-dialog.component.scss'],
  imports: [FormsModule, NgxBootstrapIconsModule],
})
export class PasswordRemovalConfirmDialogComponent extends ConfirmDialogComponent {
  updateDocument: boolean = true
  includeMetadata: boolean = true
  deleteOriginal: boolean = false

  @Input()
  override title = $localize`Remove password protection`

  @Input()
  override message =
    $localize`Create an unprotected copy or replace the existing file.`

  @Input()
  override btnCaption = $localize`Start`

  constructor() {
    super()
  }

  onUpdateDocumentChange(updateDocument: boolean) {
    this.updateDocument = updateDocument
    if (this.updateDocument) {
      this.deleteOriginal = false
      this.includeMetadata = true
    }
  }
}
