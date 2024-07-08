import { Component } from '@angular/core';
import { CustomListComponent } from '../custom-list/custom-list.component';
import { Shelf } from 'src/app/data/custom-shelf';
import { CustomShelfService } from 'src/app/services/rest/custom-shelf.service';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ToastService } from 'src/app/services/toast.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { PermissionType, PermissionsService } from 'src/app/services/permissions.service';
import { ActivatedRoute } from '@angular/router';
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component';
import { FILTER_HAS_CUSTOM_SHELF_ANY } from 'src/app/data/filter-rule-type';
import { CustomShelfEditDialogComponent } from '../../common/edit-dialog/custom-shelf-edit-dialog/custom-shelf-edit-dialog.component';
import { CustomService } from 'src/app/services/common-service/service-shelf';


@Component({
  selector: 'pngx-custom-shelf',
  templateUrl: './../custom-list/custom-list.component.html',
  styleUrls: ['./../custom-list/custom-list.component.scss'],
})
export class CustomShelfComponent extends CustomListComponent<Shelf> {
  constructor(
    customshelfService: CustomShelfService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    customService: CustomService,
    route: ActivatedRoute
  ) {
    super(
      customshelfService,
      modalService,
      CustomShelfEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_CUSTOM_SHELF_ANY,
      $localize`shelf`,
      $localize`shelf`,
      PermissionType.Warehouse,
      [
        {
          key: 'type',
          name: $localize`Type`,
          rendersHtml: true,
          valueFn: (c: Shelf) => {
            return c.type
          },
        },
      ],
      customService,
      route
    )
  }

  getDeleteMessage(object: Shelf) {
    return $localize`Do you really want to delete the Shelf "${object.name}"?`
  }
}