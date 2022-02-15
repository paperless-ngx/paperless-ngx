import { Component } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-correspondent-edit-dialog',
  templateUrl: './correspondent-edit-dialog.component.html',
  styleUrls: ['./correspondent-edit-dialog.component.scss']
})
export class CorrespondentEditDialogComponent extends EditDialogComponent<PaperlessCorrespondent> {

  constructor(service: CorrespondentService, activeModal: NgbActiveModal, toastService: ToastService) {
    super(service, activeModal, toastService)
  }

  getCreateTitle() {
    return $localize`Create new correspondent`
  }

  getEditTitle() {
    return $localize`Edit correspondent`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      matching_algorithm: new FormControl(1),
      match: new FormControl(""),
      is_insensitive: new FormControl(true)
    })
  }

}
