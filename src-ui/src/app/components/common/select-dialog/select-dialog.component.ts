import { Component, EventEmitter, Input, Output } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { SelectComponent } from '../input/select/select.component'

@Component({
  selector: 'pngx-select-dialog',
  templateUrl: './select-dialog.component.html',
  styleUrls: ['./select-dialog.component.scss'],
  imports: [SelectComponent, FormsModule, ReactiveFormsModule],
})
export class SelectDialogComponent {
  constructor(public activeModal: NgbActiveModal) {}

  @Output()
  public selectClicked = new EventEmitter()

  @Input()
  title = $localize`Select`

  @Input()
  message = $localize`Please select an object`

  @Input()
  objects: ObjectWithId[] = []

  selected: number

  cancelClicked() {
    this.activeModal.close()
  }
}
