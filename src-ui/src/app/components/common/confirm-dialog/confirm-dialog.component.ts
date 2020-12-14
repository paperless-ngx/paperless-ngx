import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-confirm-dialog',
  templateUrl: './confirm-dialog.component.html',
  styleUrls: ['./confirm-dialog.component.scss']
})
export class ConfirmDialogComponent implements OnInit {

  constructor(public activeModal: NgbActiveModal) { }

  @Output()
  public confirmClicked = new EventEmitter()

  @Input()
  title = "Confirmation"

  @Input()
  messageBold

  @Input()
  message

  @Input()
  btnClass = "btn-primary"

  @Input()
  btnCaption = "Confirm"

  ngOnInit(): void {
  }

  cancelClicked() {
    this.activeModal.close()
  }
}
