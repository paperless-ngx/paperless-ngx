import { Component, Input } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'

@Component({
  selector: 'pngx-loading-dialog',
  templateUrl: './loading-dialog.component.html',
  styleUrls: ['./loading-dialog.component.scss'],
})
export class LoadingDialogComponent {
  constructor(public activeModal: NgbActiveModal) {}

  @Input()
  verb: string = $localize`Loading`

  @Input()
  total: number

  @Input()
  current: number
}
