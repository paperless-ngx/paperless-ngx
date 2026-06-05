import { Component, inject } from '@angular/core'
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { Folder } from 'src/app/data/folder'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { FolderService } from 'src/app/services/rest/folder.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogComponent } from '../edit-dialog.component'

@Component({
  selector: 'pngx-folder-edit-dialog',
  templateUrl: './folder-edit-dialog.component.html',
  styleUrls: [],
  imports: [
    TextComponent,
    PermissionsFormComponent,
    IfOwnerDirective,
    ReactiveFormsModule,
  ],
})
export class FolderEditDialogComponent extends EditDialogComponent<Folder> {
  constructor() {
    super()
    this.service = inject(FolderService)
    this.userService = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  getCreateTitle() {
    return $localize`Create new folder`
  }

  getEditTitle() {
    return $localize`Edit folder`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      parent: new FormControl(null),
      permissions_form: new FormControl(null),
    })
  }
}
