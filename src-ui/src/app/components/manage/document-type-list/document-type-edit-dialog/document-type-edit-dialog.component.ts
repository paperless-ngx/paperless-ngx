import { Component } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-document-type-edit-dialog',
  templateUrl: './document-type-edit-dialog.component.html',
  styleUrls: ['./document-type-edit-dialog.component.scss']
})
export class DocumentTypeEditDialogComponent extends EditDialogComponent<PaperlessDocumentType> {

  constructor(service: DocumentTypeService, activeModal: NgbActiveModal, toastService: ToastService) {
    super(service, activeModal, toastService)
  }

  getCreateTitle() {
    return $localize`Create new document type`
  }

  getEditTitle() {
    return $localize`Edit document type`
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
