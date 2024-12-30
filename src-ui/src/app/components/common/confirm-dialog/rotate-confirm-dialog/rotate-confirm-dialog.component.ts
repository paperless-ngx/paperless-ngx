import { NgStyle } from '@angular/common'
import { Component } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-rotate-confirm-dialog',
  templateUrl: './rotate-confirm-dialog.component.html',
  styleUrl: './rotate-confirm-dialog.component.scss',
  imports: [NgStyle, NgxBootstrapIconsModule, SafeHtmlPipe],
})
export class RotateConfirmDialogComponent extends ConfirmDialogComponent {
  public documentID: number
  public showPDFNote: boolean = true

  // animation is better if we dont normalize yet
  public rotation: number = 0

  public get degrees(): number {
    let degrees = this.rotation % 360
    if (degrees < 0) degrees += 360
    return degrees
  }

  constructor(
    activeModal: NgbActiveModal,
    public documentService: DocumentService
  ) {
    super(activeModal)
  }

  rotate(clockwise: boolean = true) {
    this.rotation += clockwise ? 90 : -90
  }
}
