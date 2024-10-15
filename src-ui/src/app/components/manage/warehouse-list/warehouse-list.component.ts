import { Component } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { FILTER_HAS_WAREHOUSE_ANY } from 'src/app/data/filter-rule-type'
import { Warehouse } from 'src/app/data/warehouse'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { WarehouseService } from 'src/app/services/rest/warehouse.service'
import { ToastService } from 'src/app/services/toast.service'
import { WarehouseEditDialogComponent } from '../../common/edit-dialog/warehouse-edit-dialog/warehouse-edit-dialog.component'
import { ManagementListComponent } from '../management-list/management-list.component'
import { WarehouseComponent } from '../warehouse/warehouse.component'
import { ActivatedRoute } from '@angular/router'

@Component({
  selector: 'app-warehouse-list',
  templateUrl: '../warehouse/warehouse.component.html',
  styleUrls: ['../warehouse/warehouse.component.scss']
})
export class WarehouseListComponent extends WarehouseComponent<Warehouse> {
  constructor(
    warehouseService: WarehouseService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService
  ) {
    super(
      warehouseService,
      modalService,
      WarehouseEditDialogComponent,
      toastService,
      documentListViewService,
      permissionsService,
      FILTER_HAS_WAREHOUSE_ANY,
      $localize`warehouse`,
      $localize`warehouses`,
      PermissionType.Warehouse,
      [
        {
          key: 'type',
          name: $localize`Type`,
          rendersHtml: true,
          valueFn: (w: Warehouse) => {
            return w.type
          },
        },
      ]
    )
  }

  getDeleteMessage(object: Warehouse) {
    return $localize`Do you really want to delete the warehouse "${object.name}"?`
  }

}
