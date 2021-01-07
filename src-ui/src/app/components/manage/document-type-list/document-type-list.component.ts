import { Component } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { FILTER_DOCUMENT_TYPE } from 'src/app/data/filter-rule-type';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { ToastService } from 'src/app/services/toast.service';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { DocumentTypeEditDialogComponent } from './document-type-edit-dialog/document-type-edit-dialog.component';

@Component({
  selector: 'app-document-type-list',
  templateUrl: './document-type-list.component.html',
  styleUrls: ['./document-type-list.component.scss']
})
export class DocumentTypeListComponent extends GenericListComponent<PaperlessDocumentType> {

  constructor(service: DocumentTypeService, modalService: NgbModal,
    private list: DocumentListViewService,
    toastService: ToastService
  ) {
    super(service, modalService, DocumentTypeEditDialogComponent, toastService)
  }

  getDeleteMessage(object: PaperlessDocumentType) {
    return $localize`Do you really want to delete the document type "${object.name}"?`
  }


  filterDocuments(object: PaperlessDocumentType) {
    this.list.quickFilter([{rule_type: FILTER_DOCUMENT_TYPE, value: object.id.toString()}])
  }
}
