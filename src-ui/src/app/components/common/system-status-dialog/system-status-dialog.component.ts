import { Clipboard, ClipboardModule } from '@angular/cdk/clipboard'
import { Component } from '@angular/core'
import {
  NgbActiveModal,
  NgbModalModule,
  NgbPopoverModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  SystemStatus,
  SystemStatusItemStatus,
} from 'src/app/data/system-status'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'

@Component({
  selector: 'pngx-system-status-dialog',
  templateUrl: './system-status-dialog.component.html',
  styleUrl: './system-status-dialog.component.scss',
  imports: [
    NgbModalModule,
    ClipboardModule,
    NgbPopoverModule,
    NgbProgressbarModule,
    CustomDatePipe,
    FileSizePipe,
    NgxBootstrapIconsModule,
  ],
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
    this.clipboard.copy(JSON.stringify(this.status, null, 4))
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
