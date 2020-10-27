import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-correspondent-edit-dialog',
  templateUrl: './correspondent-edit-dialog.component.html',
  styleUrls: ['./correspondent-edit-dialog.component.css']
})
export class CorrespondentEditDialogComponent extends EditDialogComponent<PaperlessCorrespondent> {

  constructor(service: CorrespondentService, activeModal: NgbActiveModal, toastService: ToastService) {
    super(service, activeModal, toastService, 'correspondent')
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      automatic_classification: new FormControl(true)
    })
  }  

}
