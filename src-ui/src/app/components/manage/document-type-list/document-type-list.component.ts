import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentType } from 'src/app/data/document-type'
import { FILTER_HAS_DOCUMENT_TYPE_ANY } from 'src/app/data/filter-rule-type'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'pngx-document-type-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
})
export class DocumentTypeListComponent extends ManagementListComponent<DocumentType> {
  constructor(
    documentTypeService: DocumentTypeService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService
  ) {
    super(
      documentTypeService,
      modalService,
      DocumentTypeEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_DOCUMENT_TYPE_ANY,
      $localize`document type`,
      $localize`document types`,
      PermissionType.DocumentType,
      []
    )
  }

  getDeleteMessage(object: DocumentType) {
    return $localize`Do you really want to delete the document type "${object.name}"?`
  }
}
