import { Component } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { DocumentTypeEditDialogComponent } from './document-type-edit-dialog/document-type-edit-dialog.component';

@Component({
  selector: 'app-document-type-list',
  templateUrl: './document-type-list.component.html',
  styleUrls: ['./document-type-list.component.scss']
})
export class DocumentTypeListComponent extends GenericListComponent<PaperlessDocumentType> {

  constructor(service: DocumentTypeService, modalService: NgbModal) {
    super(service, modalService, DocumentTypeEditDialogComponent)
  }

  getObjectName(object: PaperlessDocumentType) {
    return `document type '${object.name}'`
  }

}
