import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import { TagService } from 'src/app/services/rest/tag.service'
import { randomColor } from 'src/app/utils/color'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'

@Component({
  selector: 'app-tag-edit-dialog',
  templateUrl: './tag-edit-dialog.component.html',
  styleUrls: ['./tag-edit-dialog.component.scss'],
})
export class TagEditDialogComponent extends EditDialogComponent<PaperlessTag> {
  constructor(service: TagService, activeModal: NgbActiveModal) {
    super(service, activeModal)
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
      set_permissions: new FormGroup({
        view: new FormGroup({
          users: new FormControl(null),
          groups: new FormControl(null),
        }),
        change: new FormGroup({
          users: new FormControl(null),
          groups: new FormControl(null),
        }),
      }),
    })
  }
}
