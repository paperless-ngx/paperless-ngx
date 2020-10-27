import { Component } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessTag } from 'src/app/data/paperless-tag';
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
      automatic_classification: new FormControl(true)
    })
  }

  getColours() {
    return PaperlessTag.COLOURS
  }

  getColor(id: number) {
    return PaperlessTag.COLOURS.find(c => c.id == id)
  }

}
