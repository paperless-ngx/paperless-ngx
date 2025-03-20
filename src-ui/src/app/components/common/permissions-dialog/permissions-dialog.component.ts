import { Component, EventEmitter, Input, Output } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { User } from 'src/app/data/user'
import { UserService } from 'src/app/services/rest/user.service'
import { PermissionsFormComponent } from '../input/permissions/permissions-form/permissions-form.component'
import { SwitchComponent } from '../input/switch/switch.component'

@Component({
  selector: 'pngx-permissions-dialog',
  templateUrl: './permissions-dialog.component.html',
  styleUrls: ['./permissions-dialog.component.scss'],
  imports: [
    SwitchComponent,
    PermissionsFormComponent,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class PermissionsDialogComponent {
  users: User[]
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
      merge: true,
      permissions_form: {
        owner: o.owner,
        set_permissions: o.permissions,
      },
    })
  }

  get object(): ObjectWithPermissions {
    return this.o
  }

  public form = new FormGroup({
    permissions_form: new FormControl(),
    merge: new FormControl(true),
  })

  buttonsEnabled: boolean = true

  get permissions() {
    return {
      owner: this.form.get('permissions_form').value?.owner ?? null,
      set_permissions: this.form.get('permissions_form').value
        ?.set_permissions ?? {
        view: {
          users: [],
          groups: [],
        },
        change: {
          users: [],
          groups: [],
        },
      },
    }
  }

  get hint(): string {
    if (this.object) return null
    return this.form.get('merge').value
      ? $localize`Existing owner, user and group permissions will be merged with these settings.`
      : $localize`Any and all existing owner, user and group permissions will be replaced.`
  }

  cancelClicked() {
    this.activeModal.close()
  }

  confirm() {
    this.confirmClicked.emit({
      permissions: this.permissions,
      merge: this.form.get('merge').value,
    })
  }
}
