import { Component, EventEmitter, Input, Output } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { UserService } from 'src/app/services/rest/user.service'

@Component({
  selector: 'pngx-permissions-dialog',
  templateUrl: './permissions-dialog.component.html',
  styleUrls: ['./permissions-dialog.component.scss'],
})
export class PermissionsDialogComponent {
  users: PaperlessUser[]
  private o: ObjectWithPermissions = undefined

  constructor(
    public activeModal: NgbActiveModal,
    private userService: UserService
  ) {
    this.userService.listAll().subscribe((r) => (this.users = r.results))
  }

  @Output()
  public confirmClicked = new EventEmitter()

  @Input()
  title = $localize`Set permissions`

  @Input()
  set object(o: ObjectWithPermissions) {
    this.o = o
    this.title = $localize`Edit permissions for ` + o['name']
    this.form.patchValue({
      permissions_form: {
        owner: o.owner,
        set_permissions: o.permissions,
      },
    })
  }

  get object(): ObjectWithPermissions {
    return this.o
  }

  form = new FormGroup({
    permissions_form: new FormControl(),
  })

  buttonsEnabled: boolean = true

  get permissions() {
    return {
      owner: this.form.get('permissions_form').value?.owner ?? null,
      set_permissions:
        this.form.get('permissions_form').value?.set_permissions ?? null,
    }
  }

  @Input()
  message = $localize`Note that permissions set here will override any existing permissions`

  cancelClicked() {
    this.activeModal.close()
  }
}
