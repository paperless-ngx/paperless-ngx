import { NgClass, NgTemplateOutlet } from '@angular/common'
import { Component, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import {
  NgbDropdownModule,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { CorrespondentEditDialogComponent } from 'src/app/components/common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { Correspondent } from 'src/app/data/correspondent'
import { FILTER_HAS_CORRESPONDENT_ANY } from 'src/app/data/filter-rule-type'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SortableDirective } from 'src/app/directives/sortable.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PermissionType } from 'src/app/services/permissions.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { ManagementListComponent } from '../management-list.component'

@Component({
  selector: 'pngx-correspondent-list',
  templateUrl: './../management-list.component.html',
  styleUrls: ['./../management-list.component.scss'],
  providers: [{ provide: CustomDatePipe }],
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
export class CorrespondentListComponent extends ManagementListComponent<Correspondent> {
  private readonly datePipe = inject(CustomDatePipe)

  constructor() {
    super()
    this.service = inject(CorrespondentService)
    this.editDialogComponent = CorrespondentEditDialogComponent
    this.filterRuleType = FILTER_HAS_CORRESPONDENT_ANY
    this.typeName = $localize`correspondent`
    this.typeNamePlural = $localize`correspondents`
    this.permissionType = PermissionType.Correspondent
    this.extraColumns = [
      {
        key: 'last_correspondence',
        name: $localize`Last used`,
        valueFn: (c: Correspondent) => {
          if (c.last_correspondence) {
            let date = new Date(c.last_correspondence)
            if (date.toString() == 'Invalid Date') {
              // very old date strings are unable to be parsed
              date = new Date(
                c.last_correspondence
                  ?.toString()
                  .replace(/([-+])(\d\d):\d\d:\d\d/gm, `$1$2:00`)
              )
            }
            return this.datePipe.transform(date)
          }
          return ''
        },
      },
    ]
  }

  public reloadData(): void {
    super.reloadData({ last_correspondence: true })
  }

  getDeleteMessage(object: Correspondent) {
    return $localize`Do you really want to delete the correspondent "${object.name}"?`
  }
}
