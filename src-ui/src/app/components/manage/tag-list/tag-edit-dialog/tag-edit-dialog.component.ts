import { Component } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { TAG_COLOURS, PaperlessTag } from 'src/app/data/paperless-tag';
import { TagService } from 'src/app/services/rest/tag.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-tag-edit-dialog',
  templateUrl: './tag-edit-dialog.component.html',
  styleUrls: ['./tag-edit-dialog.component.css']
})
export class TagEditDialogComponent extends EditDialogComponent<PaperlessTag> {

  constructor(service: TagService, activeModal: NgbActiveModal, toastService: ToastService) { 
    super(service, activeModal, toastService, 'tag')
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      colour: new FormControl(1),
      is_inbox_tag: new FormControl(false),
      matching_algorithm: new FormControl(1),
      match: new FormControl(""),
      is_insensitive: new FormControl(true)
    })
  }

  getColours() {
    return TAG_COLOURS
  }

  getColor(id: number) {
    return TAG_COLOURS.find(c => c.id == id)
  }

}
