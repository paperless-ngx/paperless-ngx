import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-delete-dialog',
  templateUrl: './delete-dialog.component.html',
  styleUrls: ['./delete-dialog.component.scss']
})
export class DeleteDialogComponent implements OnInit {

  constructor(public activeModal: NgbActiveModal) { }

  @Output()
  public deleteClicked = new EventEmitter()

  @Input()
  title = "Delete confirmation"

  @Input()
  message = "Do you really want to delete this?"

  @Input()
  message2

  deleteButtonEnabled = true
  seconds = 0

  delayConfirm(seconds: number) {
    this.deleteButtonEnabled = false
    this.seconds = seconds
    setTimeout(() => {
      if (this.seconds <= 1) {
        this.deleteButtonEnabled = true
      } else {
        this.delayConfirm(seconds - 1)
      }
    }, 1000)
  }

  ngOnInit(): void {
  }

  cancelClicked() {
    this.activeModal.close()
  }
}
