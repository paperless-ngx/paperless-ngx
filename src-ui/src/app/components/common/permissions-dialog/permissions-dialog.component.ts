import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { UserService } from 'src/app/services/rest/user.service'

@Component({
  selector: 'app-permissions-dialog',
  templateUrl: './permissions-dialog.component.html',
  styleUrls: ['./permissions-dialog.component.scss'],
})
export class PermissionsDialogComponent implements OnInit {
  users: PaperlessUser[]

  constructor(
    public activeModal: NgbActiveModal,
    private userService: UserService
  ) {
    this.userService.listAll().subscribe((r) => (this.users = r.results))
  }

  @Output()
  public confirmClicked = new EventEmitter()

  @Input()
  title = $localize`Set Permissions`

  form = new FormGroup({
    permissions_form: new FormControl(),
  })

  get permissions() {
    return {
      owner: this.form.get('permissions_form').value?.owner ?? null,
      set_permissions:
        this.form.get('permissions_form').value?.set_permissions ?? null,
    }
  }

  @Input()
  message = $localize`Note that permissions set here will override any existing permissions`

  ngOnInit(): void {}

  cancelClicked() {
    this.activeModal.close()
  }
}
