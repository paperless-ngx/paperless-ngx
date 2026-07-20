import { Component, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { NamedCounter } from 'src/app/data/named-counter'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { NamedCounterService } from 'src/app/services/rest/named-counter.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { TextComponent } from '../../input/text/text.component'

@Component({
  selector: 'pngx-named-counter-edit-dialog',
  templateUrl: './named-counter-edit-dialog.component.html',

  imports: [
    TextComponent,
    PermissionsFormComponent,
    IfOwnerDirective,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class NamedCounterEditDialogComponent extends EditDialogComponent<NamedCounter> {
  constructor() {
    super()
    this.service = inject(NamedCounterService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  getCreateTitle() {
    return $localize`Create new named counter`
  }

  getEditTitle() {
    return $localize`Edit named counter`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      permissions_form: new FormControl(null),
    })
  }
}
