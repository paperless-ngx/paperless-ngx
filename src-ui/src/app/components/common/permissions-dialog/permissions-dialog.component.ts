import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { PaperlessUser } from 'src/app/data/paperless-user'

@Component({
  selector: 'app-permissions-dialog',
  templateUrl: './permissions-dialog.component.html',
  styleUrls: ['./permissions-dialog.component.scss'],
})
export class PermissionsDialogComponent implements OnInit {
  constructor(public activeModal: NgbActiveModal) {}

  @Output()
  public confirmClicked = new EventEmitter()

  @Input()
  title = $localize`Set Permissions`

  form = new FormGroup({
    set_permissions: new FormGroup({
      view: new FormGroup({
        users: new FormControl([]),
        groups: new FormControl([]),
      }),
      change: new FormGroup({
        users: new FormControl([]),
        groups: new FormControl([]),
      }),
    }),
  })

  get permissions() {
    return this.form.value['set_permissions']
  }

  @Input()
  message = $localize`Note that permissions set here will override any existing permissions`

  ngOnInit(): void {}

  cancelClicked() {
    this.activeModal.close()
  }
}
