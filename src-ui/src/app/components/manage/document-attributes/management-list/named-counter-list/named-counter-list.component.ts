import { NgClass, NgTemplateOutlet } from '@angular/common'
import { Component, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import {
  NgbDropdownModule,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { NamedCounterEditDialogComponent } from 'src/app/components/common/edit-dialog/named-counter-edit-dialog/named-counter-edit-dialog.component'
import { NamedCounter } from 'src/app/data/named-counter'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { PermissionType } from 'src/app/services/permissions.service'
import { NamedCounterService } from 'src/app/services/rest/named-counter.service'
import { ManagementListComponent } from '../management-list.component'

@Component({
  selector: 'pngx-named-counter-list',
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
export class NamedCounterListComponent extends ManagementListComponent<NamedCounter> {
  constructor() {
    super()
    this.service = inject(NamedCounterService)
    this.editDialogComponent = NamedCounterEditDialogComponent
    this.typeName = $localize`named counter`
    this.typeNamePlural = $localize`named counters`
    this.permissionType = PermissionType.NamedCounter
  }

  getDeleteMessage(object: NamedCounter) {
    return $localize`Do you really want to delete the named counter "${object.name}"?`
  }
}
