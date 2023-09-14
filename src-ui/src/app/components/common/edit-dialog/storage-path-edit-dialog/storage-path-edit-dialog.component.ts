import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-storage-path-edit-dialog',
  templateUrl: './storage-path-edit-dialog.component.html',
  styleUrls: ['./storage-path-edit-dialog.component.scss'],
})
export class StoragePathEditDialogComponent extends EditDialogComponent<PaperlessStoragePath> {
  constructor(
    service: StoragePathService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  get pathHint() {
    return (
      $localize`e.g.` +
      ' <code>{created_year}-{title}</code> ' +
      $localize`or use slashes to add directories e.g.` +
      ' <code>{created_year}/{correspondent}/{title}</code>. ' +
      $localize`See <a target="_blank" href="https://docs.paperless-ngx.com/advanced_usage/#file-name-handling">documentation</a> for full list.`
    )
  }

  getCreateTitle() {
    return $localize`Create new storage path`
  }

  getEditTitle() {
    return $localize`Edit storage path`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      path: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
