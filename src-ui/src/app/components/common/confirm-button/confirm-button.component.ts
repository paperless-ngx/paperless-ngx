import {
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'

@Component({
  selector: 'pngx-confirm-button',
  templateUrl: './confirm-button.component.html',
  styleUrl: './confirm-button.component.scss',
})
export class ConfirmButtonComponent {
  @Input()
  label: string

  @Input()
  confirmMessage: string = $localize`Are you sure?`

  @Input()
  buttonClasses: string = 'btn-primary'

  @Input()
  iconName: string

  @Input()
  disabled: boolean = false

  @Output()
  confirm: EventEmitter<void> = new EventEmitter<void>()

  @ViewChild('popover') popover: NgbPopover

  public confirming: boolean = false

  public onClick(event: MouseEvent) {
    if (!this.confirming) {
      this.confirming = true
      this.popover.open()
    }

    event.preventDefault()
    event.stopImmediatePropagation()
  }

  public onConfirm(event: MouseEvent) {
    this.confirm.emit()
    this.confirming = false

    event.preventDefault()
    event.stopImmediatePropagation()
  }
}
