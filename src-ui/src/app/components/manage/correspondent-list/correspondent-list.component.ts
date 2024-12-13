import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Correspondent } from 'src/app/data/correspondent'
import { FILTER_HAS_CORRESPONDENT_ANY } from 'src/app/data/filter-rule-type'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { ToastService } from 'src/app/services/toast.service'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'

@Component({
  selector: 'pngx-correspondent-list',
  templateUrl: './../management-list/management-list.component.html',
  styleUrls: ['./../management-list/management-list.component.scss'],
  providers: [{ provide: CustomDatePipe }],
})
export class CorrespondentListComponent extends ManagementListComponent<Correspondent> {
  constructor(
    correspondentsService: CorrespondentService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    private datePipe: CustomDatePipe
  ) {
    super(
      correspondentsService,
      modalService,
      CorrespondentEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_CORRESPONDENT_ANY,
      $localize`correspondent`,
      $localize`correspondents`,
      PermissionType.Correspondent,
      [
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
    )
  }

  public reloadData(): void {
    super.reloadData({ last_correspondence: true })
  }

  getDeleteMessage(object: Correspondent) {
    return $localize`Do you really want to delete the correspondent "${object.name}"?`
  }
}
