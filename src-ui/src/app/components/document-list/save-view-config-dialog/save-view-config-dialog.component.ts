import {
  Component,
  EventEmitter,
  Input,
  OnInit,
  Output,
  inject,
} from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { User } from 'src/app/data/user'
import { UserService } from 'src/app/services/rest/user.service'
import { CheckComponent } from '../../common/input/check/check.component'
import { PermissionsFormComponent } from '../../common/input/permissions/permissions-form/permissions-form.component'
import { TextComponent } from '../../common/input/text/text.component'

@Component({
  selector: 'pngx-save-view-config-dialog',
  templateUrl: './save-view-config-dialog.component.html',
  styleUrls: ['./save-view-config-dialog.component.scss'],
  imports: [
    CheckComponent,
    TextComponent,
    PermissionsFormComponent,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class SaveViewConfigDialogComponent implements OnInit {
  private modal = inject(NgbActiveModal)
  private userService = inject(UserService)

  @Output()
  public saveClicked = new EventEmitter()

  @Input()
  error

  @Input()
  buttonsEnabled = true

  closeEnabled = false

  users: User[]

  _defaultName = ''

  get defaultName() {
    return this._defaultName
  }

  @Input()
  set defaultName(value: string) {
    this._defaultName = value
    this.saveViewConfigForm.patchValue({ name: value })
  }

  saveViewConfigForm = new FormGroup({
    name: new FormControl(''),
    showInSideBar: new FormControl(false),
    showOnDashboard: new FormControl(false),
    permissions_form: new FormControl(null),
  })

  ngOnInit(): void {
    // wait to enable close button so it doesn't steal focus from input since its the first clickable element in the DOM
    setTimeout(() => {
      this.closeEnabled = true
    })
    this.userService.listAll().subscribe((r) => {
      this.users = r.results
    })
  }

  save() {
    const formValue = this.saveViewConfigForm.value
    const saveViewConfig = {
      name: formValue.name,
      showInSideBar: formValue.showInSideBar,
      showOnDashboard: formValue.showOnDashboard,
    }
    if (formValue.permissions_form) {
      saveViewConfig['permissions_form'] = formValue.permissions_form
    }
    this.saveClicked.emit(saveViewConfig)
  }

  cancel() {
    this.modal.close()
  }
}
