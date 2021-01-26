import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { Subject } from 'rxjs';

@Component({
  selector: 'app-confirm-dialog',
  templateUrl: './confirm-dialog.component.html',
  styleUrls: ['./confirm-dialog.component.scss']
})
export class ConfirmDialogComponent implements OnInit {

  @Output()
  public confirmClicked = new EventEmitter()

  @Input()
  title = $localize`Confirmation`

  @Input()
  messageBold

  @Input()
  message

  @Input()
  btnClass = "btn-primary"

  @Input()
  btnCaption = $localize`Confirm`

  @Input()
  buttonsEnabled = true

  confirmButtonEnabled = true
  seconds = 0

  subject: Subject<boolean>

  constructor(public activeModal: NgbActiveModal) {
    this.confirmClicked.asObservable()
  }

  delayConfirm(seconds: number) {
    this.confirmButtonEnabled = false
    this.seconds = seconds
    setTimeout(() => {
      if (this.seconds <= 1) {
        this.confirmButtonEnabled = true
      } else {
        this.delayConfirm(seconds - 1)
      }
    }, 1000)
  }

  ngOnInit(): void {
  }

  cancel() {
    this.subject?.next(false)
    this.subject?.complete()
    this.activeModal.close()
  }

  confirm() {
    this.subject?.next(true)
    this.subject?.complete()
    this.confirmClicked.emit()
  }
}
