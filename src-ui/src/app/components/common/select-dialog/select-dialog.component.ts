import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { ObjectWithId } from 'src/app/data/object-with-id';

@Component({
  selector: 'app-select-dialog',
  templateUrl: './select-dialog.component.html',
  styleUrls: ['./select-dialog.component.scss']
})

export class SelectDialogComponent implements OnInit {
  constructor(public activeModal: NgbActiveModal) { }

  @Output()
  public selectClicked = new EventEmitter()

  @Input()
  title = $localize`Select`

  @Input()
  message = $localize`Please select an object`

  @Input()
  objects: ObjectWithId[] = []

  selected: number

  ngOnInit(): void {
  }

  cancelClicked() {
    this.activeModal.close()
  }
}
