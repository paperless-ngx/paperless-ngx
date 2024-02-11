import { Component } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { PaperlessSystemStatus } from 'src/app/data/system-status'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { Clipboard } from '@angular/cdk/clipboard'

@Component({
  selector: 'pngx-system-status-dialog',
  templateUrl: './system-status-dialog.component.html',
  styleUrl: './system-status-dialog.component.scss',
})
export class SystemStatusDialogComponent {
  public status: PaperlessSystemStatus

  public copied: boolean = false

  constructor(
    public activeModal: NgbActiveModal,
    private systemStatusService: SystemStatusService,
    private clipboard: Clipboard
  ) {
    this.systemStatusService.get().subscribe((status) => {
      this.status = status
    })
  }

  public close() {
    this.activeModal.close()
  }

  public copy() {
    this.clipboard.copy(JSON.stringify(this.status))
    this.copied = true
    setTimeout(() => {
      this.copied = false
    }, 3000)
  }
}
