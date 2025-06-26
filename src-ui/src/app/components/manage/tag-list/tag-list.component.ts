import { NgClass, TitleCasePipe } from '@angular/common'
import { Component, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbDropdownModule,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { Tag } from 'src/app/data/tag'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { PermissionType } from 'src/app/services/permissions.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'pngx-tag-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
  imports: [
    SortableDirective,
    PageHeaderComponent,
    TitleCasePipe,
    IfPermissionsDirective,
    SafeHtmlPipe,
    FormsModule,
    ReactiveFormsModule,
    NgClass,
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
        rendersHtml: true,
        valueFn: (t: Tag) => {
          return `<span class="badge" style="color: ${t.text_color}; background-color: ${t.color}">${t.color}</span>`
        },
      },
    ]
  }

  getDeleteMessage(object: Tag) {
    return $localize`Do you really want to delete the tag "${object.name}"?`
  }
}
