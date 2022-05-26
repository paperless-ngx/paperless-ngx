import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_DOCUMENT_TYPE } from 'src/app/data/filter-rule-type'
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'app-document-type-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
})
export class DocumentTypeListComponent extends ManagementListComponent<PaperlessDocumentType> {
  constructor(
    documentTypeService: DocumentTypeService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService
  ) {
    super(
      documentTypeService,
      modalService,
      DocumentTypeEditDialogComponent,
      toastService,
      documentListViewService,
      FILTER_DOCUMENT_TYPE,
      $localize`document type`,
      $localize`document types`,
      []
    )
  }

  getDeleteMessage(object: PaperlessDocumentType) {
    return $localize`Do you really want to delete the document type "${object.name}"?`
  }
}
