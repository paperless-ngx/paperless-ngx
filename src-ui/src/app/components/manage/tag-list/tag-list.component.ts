import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import { QueryParamsService } from 'src/app/services/query-params.service'
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
    queryParamsService: QueryParamsService
  ) {
    super(
      tagService,
      modalService,
      TagEditDialogComponent,
      toastService,
      queryParamsService,
      FILTER_HAS_TAGS_ALL,
      $localize`tag`,
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
