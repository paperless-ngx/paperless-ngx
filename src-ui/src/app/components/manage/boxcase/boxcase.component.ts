import { Component, Renderer2, ViewContainerRef } from '@angular/core'
import { BoxService } from 'src/app/services/rest/box.service'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { PermissionType, PermissionsService } from 'src/app/services/permissions.service'
import { Box } from 'src/app/data/box'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { BoxEditDialogComponent } from '../../common/edit-dialog/box-edit-dialog/box-edit-dialog.component'
import { FILTER_HAS_BOX_ANY } from 'src/app/data/filter-rule-type'
import { ActivatedRoute, Router } from '@angular/router'
import { ManagementListComponent } from '../management-list/management-list.component'
import { takeUntil } from 'rxjs/operators'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { Warehouse } from '../../../data/warehouse'
import { WarehouseComponent } from '../warehouse/warehouse.component'
import { ShelfComponent } from '../shelf/shelf.component'

@Component({
  selector: 'pngx-boxcase',
  templateUrl: './boxcase.component.html',
  styleUrls: ['./boxcase.component.scss'],
})
export class BoxCaseComponent extends ManagementListComponent<Box> {
  warehousePath: Warehouse[] = []

  constructor(
    private boxService: BoxService,
    modalService: NgbModal,
    toastService: ToastService,
    documentListViewService: DocumentListViewService,
    permissionsService: PermissionsService,
    private route: ActivatedRoute,
    private router: Router,
    private viewContainer: ViewContainerRef,
    private renderer: Renderer2,
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
    )
  }

  openCreateDialog() {
    var activeModal = this.getModalService().open(this.getEditDialogComponent(), {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = { parent_warehouse: this.id, type: 'Boxcase' }
    activeModal.componentInstance.dialogMode = EditDialogMode.CREATE
    activeModal.componentInstance.succeeded.subscribe(() => {
      this.reloadData()
      // this.getDocuments(this.id);
      this.getToastService().showInfo(
        $localize`Successfully created ${this.typeName}.`,
      )
    })
    activeModal.componentInstance.failed.subscribe((e) => {
      this.getToastService().showError(
        $localize`Error occurred while creating ${this.typeName}.`,
        e,
      )
    })
  }

  renderWarehouse() {

    const treeWarehouse = document.querySelector('.warehouse-tree')
    const warehouseElement = document.querySelector('.warehouse')
    warehouseElement.innerHTML = ''
    const warehouseRootElement = this.viewContainer.createComponent(WarehouseComponent)

    const componentElement = warehouseRootElement.location.nativeElement
    const treeWarehouseRoot = componentElement.querySelector('.warehouse-tree')
    treeWarehouseRoot.innerHTML = ''
    this.renderer.appendChild(treeWarehouseRoot, treeWarehouse)
    this.renderer.appendChild(warehouseElement, componentElement)

  }
  renderShelf(){

    const treeWarehouseOld = document.querySelector('.warehouse-tree');
    const warehouseElement = document.querySelector('.warehouse');
    warehouseElement.innerHTML = ''
    const shelfElement = this.viewContainer.createComponent(ShelfComponent);

    const componentElement = shelfElement.location.nativeElement
    const treeWarehouseNew= componentElement.querySelector('.warehouse-tree');

    this.renderer.appendChild(treeWarehouseNew, treeWarehouseOld)
    this.renderer.appendChild(warehouseElement, componentElement)

  }

  goToWarehouseRoot(param) {
    this.router.navigate(['/warehouses', 'root'])
    this.renderWarehouse()

  }



  reloadData() {
    let type = ''
    let params = {}
    this.route.params.subscribe(param => {
      this.id = +param['id']
    })
    this.route.queryParams.subscribe(query_param => {
      type = query_param['type']
    })
    let warehousePathList
    if (this.id) {
      this.boxService.getWarehousePath(this.id).subscribe(
        (warehouse) => {
          warehousePathList = warehouse
          this.warehousePath = warehousePathList.results
        })
    }

    params['type__iexact'] = 'Boxcase'
    params['parent_warehouse'] = this.id
    // params['parent_warehouse']
    this.isLoading = true
    this.getService()
      .listFilteredCustom(
        this.page,
        null,
        this.sortField,
        params,
        this.sortReverse,
        this.nameFilter,
        true,
      )
      .pipe(takeUntil(this.getUnsubscribeNotifier()))
      .subscribe((c) => {
        this.data = c.results
        this.collectionSize = c.count
        this.isLoading = false
      })
  }


  getDeleteMessage(object: Box) {
    return $localize`Do you really want to delete the Boxcase "${object.name}"?`
  }


  goToShelf(w: Warehouse) {
    if (w.type == 'Warehouse') {
      this.router.navigate(['/warehouses', w.id], { queryParams: { type: 'Shelf' } })
      this.renderShelf()
    }
  }
}
