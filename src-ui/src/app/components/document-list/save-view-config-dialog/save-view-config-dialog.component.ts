import {
  Component,
  EventEmitter,
  Input,
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
import { User } from 'src/app/data/user'
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
  private errorSignal = signal(undefined)
  private buttonsEnabledSignal = signal(true)
  private defaultNameSignal = signal('')

  @Output()
  public saveClicked = new EventEmitter()

  @Input()
  get error() {
    return this.errorSignal()
  }

  set error(error) {
    this.errorSignal.set(error)
  }

  @Input()
  get buttonsEnabled(): boolean {
    return this.buttonsEnabledSignal()
  }

  set buttonsEnabled(buttonsEnabled: boolean) {
    this.buttonsEnabledSignal.set(buttonsEnabled)
  }

  closeEnabled = false

  users: User[]

  get defaultName() {
    return this.defaultNameSignal()
  }

  @Input()
  set defaultName(value: string) {
    this.defaultNameSignal.set(value)
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
