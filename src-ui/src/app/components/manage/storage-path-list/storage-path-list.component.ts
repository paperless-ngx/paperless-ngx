import { NgClass, NgTemplateOutlet, TitleCasePipe } from '@angular/common'
import { Component, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbDropdownModule,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { FILTER_HAS_STORAGE_PATH_ANY } from 'src/app/data/filter-rule-type'
import { StoragePath } from 'src/app/data/storage-path'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { PermissionType } from 'src/app/services/permissions.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { ClearableBadgeComponent } from '../../common/clearable-badge/clearable-badge.component'
import { StoragePathEditDialogComponent } from '../../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'pngx-storage-path-list',
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
    NgTemplateOutlet,
    NgbDropdownModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
    ClearableBadgeComponent,
  ],
})
export class StoragePathListComponent extends ManagementListComponent<StoragePath> {
  constructor() {
    super()
    this.service = inject(StoragePathService)
    this.editDialogComponent = StoragePathEditDialogComponent
    this.filterRuleType = FILTER_HAS_STORAGE_PATH_ANY
    this.typeName = $localize`storage path`
    this.typeNamePlural = $localize`storage paths`
    this.permissionType = PermissionType.StoragePath
    this.extraColumns = [
      {
        key: 'path',
        name: $localize`Path`,
        hideOnMobile: true,
        monospace: true,
        valueFn: (c: StoragePath) => {
          return `${c.path?.slice(0, 49)}${c.path?.length > 50 ? '...' : ''}`
        },
      },
    ]
  }

  getDeleteMessage(object: StoragePath) {
    return $localize`Do you really want to delete the storage path "${object.name}"?`
  }
}
