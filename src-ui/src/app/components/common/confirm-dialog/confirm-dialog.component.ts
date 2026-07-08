import { DecimalPipe } from '@angular/common'
import {
  Component,
  EventEmitter,
  Input,
  Output,
  inject,
  signal,
} from '@angular/core'
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

  private titleSignal = signal($localize`Confirmation`)
  private messageBoldSignal = signal<string>(undefined)
  private messageSignal = signal<string>(undefined)
  private btnClassSignal = signal('btn-primary')
  private btnCaptionSignal = signal($localize`Confirm`)
  private alternativeBtnClassSignal = signal('btn-secondary')
  private alternativeBtnCaptionSignal = signal<string>(undefined)
  private cancelBtnClassSignal = signal('btn-outline-secondary')
  private cancelBtnCaptionSignal = signal($localize`Cancel`)
  private buttonsEnabledSignal = signal(true)

  @Output()
  public confirmClicked = new EventEmitter()

  @Output()
  public alternativeClicked = new EventEmitter()

  @Input()
  get title(): string {
    return this.titleSignal()
  }

  set title(title: string) {
    this.titleSignal.set(title)
  }

  @Input()
  get messageBold(): string {
    return this.messageBoldSignal()
  }

  set messageBold(messageBold: string) {
    this.messageBoldSignal.set(messageBold)
  }

  @Input()
  get message(): string {
    return this.messageSignal()
  }

  set message(message: string) {
    this.messageSignal.set(message)
  }

  @Input()
  get btnClass(): string {
    return this.btnClassSignal()
  }

  set btnClass(btnClass: string) {
    this.btnClassSignal.set(btnClass)
  }

  @Input()
  get btnCaption(): string {
    return this.btnCaptionSignal()
  }

  set btnCaption(btnCaption: string) {
    this.btnCaptionSignal.set(btnCaption)
  }

  @Input()
  get alternativeBtnClass(): string {
    return this.alternativeBtnClassSignal()
  }

  set alternativeBtnClass(alternativeBtnClass: string) {
    this.alternativeBtnClassSignal.set(alternativeBtnClass)
  }

  @Input()
  get alternativeBtnCaption(): string {
    return this.alternativeBtnCaptionSignal()
  }

  set alternativeBtnCaption(alternativeBtnCaption: string) {
    this.alternativeBtnCaptionSignal.set(alternativeBtnCaption)
  }

  @Input()
  get cancelBtnClass(): string {
    return this.cancelBtnClassSignal()
  }

  set cancelBtnClass(cancelBtnClass: string) {
    this.cancelBtnClassSignal.set(cancelBtnClass)
  }

  @Input()
  get cancelBtnCaption(): string {
    return this.cancelBtnCaptionSignal()
  }

  set cancelBtnCaption(cancelBtnCaption: string) {
    this.cancelBtnCaptionSignal.set(cancelBtnCaption)
  }

  @Input()
  get buttonsEnabled(): boolean {
    return this.buttonsEnabledSignal()
  }

  set buttonsEnabled(buttonsEnabled: boolean) {
    this.buttonsEnabledSignal.set(buttonsEnabled)
  }

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
