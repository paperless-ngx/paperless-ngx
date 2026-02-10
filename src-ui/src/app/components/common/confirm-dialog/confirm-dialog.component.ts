import { DecimalPipe } from '@angular/common'
import { Component, EventEmitter, Input, Output, inject } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-confirm-dialog',
  templateUrl: './confirm-dialog.component.html',
  styleUrls: ['./confirm-dialog.component.scss'],
  imports: [DecimalPipe],
})
export class ConfirmDialogComponent extends LoadingComponentWithPermissions {
  activeModal = inject(NgbActiveModal)

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
