import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { ArchiveFont } from 'src/app/data/archive-font'
import { TagService } from 'src/app/services/rest/tag.service'
import { randomColor } from 'src/app/utils/color'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ArchiveFontService } from 'src/app/services/rest/archive-font.service'

@Component({
  selector: 'pngx-archive-font-edit-dialog',
  templateUrl: './archive-font-edit-dialog.component.html',
  styleUrls: ['./archive-font-edit-dialog.component.scss'],
})
export class ArchiveFontEditDialogComponent extends EditDialogComponent<ArchiveFont> {
  constructor(
    service: ArchiveFontService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getCreateTitle() {
    return $localize`Create new font language`
  }

  getEditTitle() {
    return $localize`Edit font language`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      // color: new FormControl(randomColor()),
      // is_inbox_tag: new FormControl(false),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
