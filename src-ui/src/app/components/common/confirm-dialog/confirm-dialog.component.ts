import { Component, EventEmitter, Input, Output } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { interval, Subject, switchMap, take } from 'rxjs'

@Component({
  selector: 'app-confirm-dialog',
  templateUrl: './confirm-dialog.component.html',
  styleUrls: ['./confirm-dialog.component.scss'],
})
export class ConfirmDialogComponent {
  constructor(public activeModal: NgbActiveModal) {}

  @Output()
  public confirmClicked = new EventEmitter()

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
  buttonsEnabled = true

  confirmButtonEnabled = true
  seconds = 0
  secondsTotal = 0

  confirmSubject: Subject<boolean>

  delayConfirm(seconds: number) {
    const refreshInterval = 0.15 // s

    this.secondsTotal = seconds
    this.seconds = seconds

    interval(refreshInterval * 1000)
      .pipe(
        take(this.secondsTotal / refreshInterval + 2) // need 2 more for animation to complete after 0
      )
      .subscribe((count) => {
        this.seconds = Math.max(
          0,
          this.secondsTotal - refreshInterval * (count + 1)
        )
        this.confirmButtonEnabled =
          this.secondsTotal - refreshInterval * count < 0
      })
  }

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
}
