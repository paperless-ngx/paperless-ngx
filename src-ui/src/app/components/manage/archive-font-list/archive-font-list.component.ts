import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import {
  FILTER_HAS_ARCHIVE_FONT_ANY,
} from 'src/app/data/filter-rule-type'
import { ArchiveFont } from 'src/app/data/archive-font'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { ArchiveFontService } from 'src/app/services/rest/archive-font.service'
import { ToastService } from 'src/app/services/toast.service'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'
import {
  ArchiveFontEditDialogComponent
} from '../../common/edit-dialog/archive-font-edit-dialog/archive-font-edit-dialog.component'

@Component({
  selector: 'pngx-archive-font-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
})
export class ArchiveFontListComponent extends ManagementListComponent<ArchiveFont> {
  constructor(
    archiveFontService: ArchiveFontService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService
  ) {
    super(
      archiveFontService,
      modalService,
      ArchiveFontEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_ARCHIVE_FONT_ANY,
      $localize`archive font`,
      $localize`archive fonts`,
      PermissionType.ArchiveFont,
      [
        // {
        //   key: 'color',
        //   name: $localize`Color`,
        //   rendersHtml: true,
        //   valueFn: (t: ArchiveFont) => {
        //     return `<span class="badge" style="color: ${t.text_color}; background-color: ${t.color}">${t.color}</span>`
        //   },
        // },
      ]
    )
  }

  getDeleteMessage(object: ArchiveFont) {
    return $localize`Do you really want to delete the archive font "${object.name}"?`
  }
}
