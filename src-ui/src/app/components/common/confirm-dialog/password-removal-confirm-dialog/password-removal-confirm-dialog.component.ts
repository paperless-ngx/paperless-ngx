import { Component } from '@angular/core'
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

  constructor() {
    super()
    this.title = $localize`Remove password protection`
    this.message = $localize`Create an unprotected copy or replace the existing file.`
    this.btnCaption = $localize`Start`
  }

  onUpdateDocumentChange(updateDocument: boolean) {
    this.updateDocument = updateDocument
    if (this.updateDocument) {
      this.deleteOriginal = false
      this.includeMetadata = true
    }
  }
}
