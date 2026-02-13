import { NgClass, NgTemplateOutlet } from '@angular/common'
import { Component, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import {
  NgbDropdownModule,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TagEditDialogComponent } from 'src/app/components/common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { Tag } from 'src/app/data/tag'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { PermissionType } from 'src/app/services/permissions.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { ManagementListComponent } from '../management-list.component'

@Component({
  selector: 'pngx-tag-list',
  templateUrl: './../management-list.component.html',
  styleUrls: ['./../management-list.component.scss'],
  imports: [
    SortableDirective,
    IfPermissionsDirective,
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    NgClass,
    NgTemplateOutlet,
    NgbDropdownModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
  ],
})
export class TagListComponent extends ManagementListComponent<Tag> {
  constructor() {
    super()
    this.service = inject(TagService)
    this.editDialogComponent = TagEditDialogComponent
    this.filterRuleType = FILTER_HAS_TAGS_ALL
    this.typeName = $localize`tag`
    this.typeNamePlural = $localize`tags`
    this.permissionType = PermissionType.Tag
    this.extraColumns = [
      {
        key: 'color',
        name: $localize`Color`,
        badgeFn: (t: Tag) => ({
          text: t.color,
          textColor: t.text_color,
          backgroundColor: t.color,
        }),
      },
    ]
  }

  getDeleteMessage(object: Tag) {
    return $localize`Do you really want to delete the tag "${object.name}"?`
  }

  override reloadData(extraParams: { [key: string]: any } = null) {
    const params = this.nameFilter?.length
      ? extraParams
      : { ...extraParams, is_root: true }
    super.reloadData(params)
  }

  filterData(data: Tag[]) {
    if (!this.nameFilter?.length) {
      return data.filter((tag) => !tag.parent)
    }

    // When filtering by name, exclude children if their parent is also present
    const availableIds = new Set(data.map((tag) => tag.id))
    return data.filter((tag) => !tag.parent || !availableIds.has(tag.parent))
  }

  protected override getSelectableIDs(tags: Tag[]): number[] {
    const ids: number[] = []
    for (const tag of tags.filter(Boolean)) {
      if (tag.id != null) {
        ids.push(tag.id)
      }
      if (Array.isArray(tag.children) && tag.children.length) {
        ids.push(...this.getSelectableIDs(tag.children))
      }
    }
    return ids
  }
}
