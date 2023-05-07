import { Component, EventEmitter, Input, Output } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'

@Component({
  selector: 'show-description-dialog',
  templateUrl: './show-description-dialog.component.html',
  styleUrls: ['./show-description-dialog.component.scss'],
})
export class ShowDescriptionDialogComponent {
  constructor(private modal: NgbActiveModal) {}

  @Output()
  public filterClicked = new EventEmitter()

  @Input()
  model

  filter() {
    this.filterClicked.emit()
    this.modal.close()
  }

  cancel() {
    this.modal.close()
  }
}
