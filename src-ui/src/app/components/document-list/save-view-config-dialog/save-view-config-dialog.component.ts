import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-save-view-config-dialog',
  templateUrl: './save-view-config-dialog.component.html',
  styleUrls: ['./save-view-config-dialog.component.scss']
})
export class SaveViewConfigDialogComponent implements OnInit {

  constructor(private modal: NgbActiveModal) { }

  @Output()
  public saveClicked = new EventEmitter()

  _defaultName = ""

  get defaultName() {
    return this._defaultName
  }

  @Input()
  set defaultName(value: string) {
    this._defaultName = value
    this.saveViewConfigForm.patchValue({name: value})
  }
  

  saveViewConfigForm = new FormGroup({
    name: new FormControl(''),
    showInSideBar: new FormControl(false),
    showOnDashboard: new FormControl(false),
  })

  ngOnInit(): void {
  }

  save() {
    this.saveClicked.emit(this.saveViewConfigForm.value)
  }

  cancel() {
    this.modal.close()
  }
}
