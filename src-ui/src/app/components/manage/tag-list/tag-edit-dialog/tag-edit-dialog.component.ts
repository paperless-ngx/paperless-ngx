import { Component } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { TagService } from 'src/app/services/rest/tag.service';
import { ToastService } from 'src/app/services/toast.service';
import { randomColor } from 'src/app/utils/color';

@Component({
  selector: 'app-tag-edit-dialog',
  templateUrl: './tag-edit-dialog.component.html',
  styleUrls: ['./tag-edit-dialog.component.scss']
})
export class TagEditDialogComponent extends EditDialogComponent<PaperlessTag> {

  constructor(service: TagService, activeModal: NgbActiveModal, toastService: ToastService) {
    super(service, activeModal, toastService)
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
      matching_algorithm: new FormControl(1),
      match: new FormControl(""),
      is_insensitive: new FormControl(true)
    })
  }

}
