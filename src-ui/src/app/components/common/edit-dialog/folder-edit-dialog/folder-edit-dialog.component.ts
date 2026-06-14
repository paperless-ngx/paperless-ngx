import { Component, Input, inject } from '@angular/core'
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { Folder } from 'src/app/data/folder'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { FolderService } from 'src/app/services/rest/folder.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { flattenFolders } from 'src/app/utils/flatten-folders'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { EditDialogComponent } from '../edit-dialog.component'

@Component({
  selector: 'pngx-folder-edit-dialog',
  templateUrl: './folder-edit-dialog.component.html',
  styleUrls: [],
  imports: [
    TextComponent,
    SelectComponent,
    PermissionsFormComponent,
    IfOwnerDirective,
    ReactiveFormsModule,
  ],
})
export class FolderEditDialogComponent extends EditDialogComponent<Folder> {
  @Input()
  folders: Folder[] = []

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

  get parentOptions(): Folder[] {
    if (!this.folders?.length) return []

    const blocked = new Set<number>()
    if (this.object?.id) {
      blocked.add(this.object.id)
      this.collectDescendantIds(this.object, blocked)
    }

    return flattenFolders(this.folders).filter(
      (folder) => !blocked.has(folder.id)
    )
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      parent: new FormControl(null),
      permissions_form: new FormControl(null),
    })
  }

  private collectDescendantIds(folder: Folder, blocked: Set<number>): void {
    for (const child of folder.children ?? []) {
      blocked.add(child.id)
      this.collectDescendantIds(child, blocked)
    }
  }
}
