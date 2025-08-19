import { NgClass, TitleCasePipe } from '@angular/common'
import { Component, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbDropdownModule,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { DocumentType } from 'src/app/data/document-type'
import { FILTER_HAS_DOCUMENT_TYPE_ANY } from 'src/app/data/filter-rule-type'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { PermissionType } from 'src/app/services/permissions.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'pngx-document-type-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
  imports: [
    SortableDirective,
    PageHeaderComponent,
    TitleCasePipe,
    IfPermissionsDirective,
    FormsModule,
    ReactiveFormsModule,
    NgClass,
    NgbDropdownModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
  ],
})
export class DocumentTypeListComponent extends ManagementListComponent<DocumentType> {
  constructor() {
    super()
    this.service = inject(DocumentTypeService)
    this.editDialogComponent = DocumentTypeEditDialogComponent
    this.filterRuleType = FILTER_HAS_DOCUMENT_TYPE_ANY
    this.typeName = $localize`document type`
    this.typeNamePlural = $localize`document types`
    this.permissionType = PermissionType.DocumentType
  }

  getDeleteMessage(object: DocumentType) {
    return $localize`Do you really want to delete the document type "${object.name}"?`
  }
}
