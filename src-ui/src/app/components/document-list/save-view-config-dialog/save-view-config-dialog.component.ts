import {
  Component,
  EventEmitter,
  OnInit,
  Output,
  inject,
  signal,
} from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import {
  DEFAULT_SAVED_VIEW_ICON,
  SAVED_VIEW_ICONS,
} from 'src/app/data/saved-view-icons'
import { User } from 'src/app/data/user'
import { CheckComponent } from '../../common/input/check/check.component'
import { PermissionsFormComponent } from '../../common/input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../common/input/select/select.component'
import { TextComponent } from '../../common/input/text/text.component'

@Component({
  selector: 'pngx-save-view-config-dialog',
  templateUrl: './save-view-config-dialog.component.html',
  styleUrls: ['./save-view-config-dialog.component.scss'],
  imports: [
    CheckComponent,
    SelectComponent,
    TextComponent,
    PermissionsFormComponent,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class SaveViewConfigDialogComponent implements OnInit {
  private modal = inject(NgbActiveModal)
  readonly error = signal(undefined)
  readonly buttonsEnabled = signal(true)
  readonly defaultName = signal('')
  readonly closeEnabled = signal(false)

  @Output()
  public saveClicked = new EventEmitter()

  users: User[]
  readonly savedViewIcons = SAVED_VIEW_ICONS

  setDefaultName(value: string) {
    this.defaultName.set(value)
    this.saveViewConfigForm.patchValue({ name: value })
  }

  saveViewConfigForm = new FormGroup({
    name: new FormControl(''),
    icon: new FormControl(DEFAULT_SAVED_VIEW_ICON),
    showInSideBar: new FormControl(false),
    showOnDashboard: new FormControl(false),
    permissions_form: new FormControl(null),
  })

  ngOnInit(): void {
    // wait to enable close button so it doesn't steal focus from input since its the first clickable element in the DOM
    setTimeout(() => {
      this.closeEnabled.set(true)
    })
  }

  save() {
    const formValue = this.saveViewConfigForm.value
    const saveViewConfig = {
      name: formValue.name,
      icon: formValue.icon,
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
