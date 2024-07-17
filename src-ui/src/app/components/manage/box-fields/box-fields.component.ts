import { Component } from '@angular/core';
import { BoxListComponent } from '../box-list/box-list.component';
import { BoxService } from 'src/app/services/rest/box.service';
import { ToastService } from 'src/app/services/toast.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { PermissionType, PermissionsService } from 'src/app/services/permissions.service';
import { Box } from 'src/app/data/box';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { BoxEditDialogComponent } from '../../common/edit-dialog/box-edit-dialog/box-edit-dialog.component';
import { FILTER_HAS_BOX_ANY } from 'src/app/data/filter-rule-type';
import { BoxsServices } from 'src/app/services/common-service/service-box';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'pngx-box-fields',
  templateUrl: './../box-list/box-list.component.html',
  styleUrls: ['./../box-list/box-list.component.scss'],
})
export class BoxFieldsComponent extends BoxListComponent<Box> {
  constructor(
    boxService: BoxService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    boxsService: BoxsServices,
    route: ActivatedRoute
  ) {
    super(
      boxService,
      modalService,
      BoxEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_BOX_ANY,
      $localize`boxcase`,
      $localize`boxcases`,
      PermissionType.Warehouse,
      [
        {
          key: 'type',
          name: $localize`Type`,
          rendersHtml: true,
          valueFn: (c: Box) => {
            return c.type
          },
        },
      ],
      boxsService,
      route
    )
  }

  getDeleteMessage(object: Box) {
    return $localize`Do you really want to delete the Boxcase "${object.name}"?`
  }
}