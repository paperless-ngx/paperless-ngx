import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_HAS_ARCHIVE_FONT_ANY, FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { FontLanguage } from 'src/app/data/font-language'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { FontLanguageService } from 'src/app/services/rest/font-language.service'
import { ToastService } from 'src/app/services/toast.service'
import { FontLanguageEditDialogComponent } from '../../common/edit-dialog/font-language-edit-dialog/font-language-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'


@Component({
  selector: 'pngx-font-language-list',
  templateUrl: '/font-language-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
})
export class FontLanguageListComponent extends ManagementListComponent<FontLanguage> {
  constructor(
    fontLanguageService: FontLanguageService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService
  ) {
    super(
      fontLanguageService,
      modalService,
      FontLanguageEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_ARCHIVE_FONT_ANY,
      $localize`font language`,
      $localize`font languages`,
      PermissionType.FontLanguage,
      [
        // {
        //   key: 'color',
        //   name: $localize`Color`,
        //   rendersHtml: true,
        //   valueFn: (t: Tag) => {
        //     return `<span class="badge" style="color: ${t.text_color}; background-color: ${t.color}">${t.color}</span>`
        //   },
        // },
      ]
    )
  }

  getDeleteMessage(object: FontLanguage) {
    return $localize`Do you really want to delete the font language "${object.name}"?`
  }
}
