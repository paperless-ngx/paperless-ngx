import { Component, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { SettingsService } from 'src/app/services/settings.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-reprocess-confirm-dialog',
  templateUrl: './reprocess-confirm-dialog.component.html',
  imports: [FormsModule],
})
export class ReprocessConfirmDialogComponent extends ConfirmDialogComponent {
  private settings = inject(SettingsService)

  remoteOcr: boolean = false

  public get showRemoteOcr(): boolean {
    // Hidden when it is not configured, or when it already handles every document anyway.
    return this.settings.remoteOCRIsSelectable
  }
}
