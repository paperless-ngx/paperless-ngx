import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { ToastService } from 'src/app/services/toast.service'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'app-tag-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
})
export class TagListComponent extends ManagementListComponent<PaperlessTag> {
  constructor(
    tagService: TagService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService
  ) {
    super(
      tagService,
      modalService,
      TagEditDialogComponent,
      toastService,
      documentListViewService,
      FILTER_HAS_TAGS_ALL,
      $localize`tag`,
      $localize`tags`,
      [
        {
          key: 'color',
          name: $localize`Color`,
          rendersHtml: true,
          valueFn: (t: PaperlessTag) => {
            return `<span class="badge" style="color: ${t.text_color}; background-color: ${t.color}">${t.color}</span>`
          },
        },
      ]
    )
  }

  getDeleteMessage(object: PaperlessTag) {
    return $localize`Do you really want to delete the tag "${object.name}"?`
  }
}
