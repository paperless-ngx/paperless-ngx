import { Component, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Group } from 'src/app/data/group'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { TextComponent } from '../../input/text/text.component'
import { PermissionsSelectComponent } from '../../permissions-select/permissions-select.component'

@Component({
  selector: 'pngx-group-edit-dialog',
  templateUrl: './group-edit-dialog.component.html',
  styleUrls: ['./group-edit-dialog.component.scss'],
  imports: [
    PermissionsSelectComponent,
    TextComponent,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class GroupEditDialogComponent extends EditDialogComponent<Group> {
  constructor() {
    super()
    this.service = inject(GroupService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  getCreateTitle() {
    return $localize`Create new user group`
  }

  getEditTitle() {
    return $localize`Edit user group`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      permissions: new FormControl(null),
    })
  }
}
