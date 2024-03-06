import { Component, Input } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import {
  SystemStatus,
  SystemStatusItemStatus,
} from 'src/app/data/system-status'
import { SystemStatusService } from 'src/app/services/system-status.service'
import { Clipboard } from '@angular/cdk/clipboard'

@Component({
  selector: 'pngx-system-status-dialog',
  templateUrl: './system-status-dialog.component.html',
  styleUrl: './system-status-dialog.component.scss',
})
export class SystemStatusDialogComponent {
  public SystemStatusItemStatus = SystemStatusItemStatus
  public status: SystemStatus

  public copied: boolean = false

  constructor(
    public activeModal: NgbActiveModal,
    private clipboard: Clipboard
  ) {}

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

  public isStale(dateStr: string, hours: number = 24): boolean {
    const date = new Date(dateStr)
    const now = new Date()
    return now.getTime() - date.getTime() > hours * 60 * 60 * 1000
  }
}
