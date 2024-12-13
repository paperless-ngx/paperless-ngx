import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { Tag } from 'src/app/data/tag'
import { TagService } from 'src/app/services/rest/tag.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { randomColor } from 'src/app/utils/color'

@Component({
  selector: 'pngx-tag-edit-dialog',
  templateUrl: './tag-edit-dialog.component.html',
  styleUrls: ['./tag-edit-dialog.component.scss'],
})
export class TagEditDialogComponent extends EditDialogComponent<Tag> {
  constructor(
    service: TagService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getCreateTitle() {
    return $localize`Create new tag`
  }

  getEditTitle() {
    return $localize`Edit tag`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      color: new FormControl(randomColor()),
      is_inbox_tag: new FormControl(false),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
