import { Component, EventEmitter, Input, Output } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { interval, Subject, take } from 'rxjs'

@Component({
  selector: 'pngx-confirm-dialog',
  templateUrl: './confirm-dialog.component.html',
  styleUrls: ['./confirm-dialog.component.scss'],
})
export class ConfirmDialogComponent {
  constructor(public activeModal: NgbActiveModal) {}

  @Output()
  public confirmClicked = new EventEmitter()

  @Output()
  public alternativeClicked = new EventEmitter()

  @Input()
  title = $localize`Confirmation`

  @Input()
  messageBold

  @Input()
  message

  @Input()
  btnClass = 'btn-primary'

  @Input()
  btnCaption = $localize`Confirm`

  @Input()
  alternativeBtnClass = 'btn-secondary'

  @Input()
  alternativeBtnCaption

  @Input()
  cancelBtnClass = 'btn-outline-secondary'

  @Input()
  cancelBtnCaption = $localize`Cancel`

  @Input()
  buttonsEnabled = true

  confirmButtonEnabled = true
  alternativeButtonEnabled = true
  seconds = 0
  secondsTotal = 0

  confirmSubject: Subject<boolean>
  alternativeSubject: Subject<boolean>

  cancel() {
    this.confirmSubject?.next(false)
    this.confirmSubject?.complete()
    this.activeModal.close()
  }

  confirm() {
    this.confirmClicked.emit()
    this.confirmSubject?.next(true)
    this.confirmSubject?.complete()
  }

  alternative() {
    this.alternativeClicked.emit()
    this.alternativeSubject?.next(true)
    this.alternativeSubject?.complete()
  }
}
