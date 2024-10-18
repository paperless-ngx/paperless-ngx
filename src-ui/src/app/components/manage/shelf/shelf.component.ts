import { Component, Renderer2, ViewChild, ViewContainerRef } from '@angular/core'
import { Shelf } from 'src/app/data/custom-shelf';
import { CustomShelfService } from 'src/app/services/rest/custom-shelf.service';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ToastService } from 'src/app/services/toast.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { PermissionType, PermissionsService } from 'src/app/services/permissions.service';
import { ActivatedRoute, Router } from '@angular/router'
import { FILTER_HAS_CUSTOM_SHELF_ANY } from 'src/app/data/filter-rule-type';
import { CustomShelfEditDialogComponent } from '../../common/edit-dialog/custom-shelf-edit-dialog/custom-shelf-edit-dialog.component';
import { ManagementListComponent } from '../management-list/management-list.component'
import { takeUntil } from 'rxjs/operators'
import { BoxCaseComponent } from '../boxcase/boxcase.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { Warehouse } from '../../../data/warehouse'
import { WarehouseService } from '../../../services/rest/warehouse.service'
import { WarehouseComponent } from '../warehouse/warehouse.component'


@Component({
  selector: 'pngx-shelf',
  templateUrl: './shelf.component.html',
  styleUrls: ['./shelf.component.scss'],
})
export class ShelfComponent extends ManagementListComponent<Shelf> {
  @ViewChild('warehouseTree', { read: ViewContainerRef }) container!: ViewContainerRef
  warehousePath: Warehouse[] = []
  constructor(
    private customshelfService: CustomShelfService,
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
    )
  }
  openCreateDialog() {
    var activeModal = this.getModalService().open(this.getEditDialogComponent(), {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = { parent_warehouse: this.id }
    activeModal.componentInstance.dialogMode = EditDialogMode.CREATE
    activeModal.componentInstance.succeeded.subscribe(() => {
      this.reloadData()
      // this.getDocuments(this.id);
      this.getToastService().showInfo(
        $localize`Successfully created ${this.typeName}.`
      )
    })
    activeModal.componentInstance.failed.subscribe((e) => {
      this.getToastService().showError(
        $localize`Error occurred while creating ${this.typeName}.`,
        e
      )
    })
  }
  renderBoxcase(){

    const tableFilterContent = document.querySelector('.warehouse-tree');
    const warehouseElement = document.querySelector('.warehouse');
    warehouseElement.innerHTML = ''
    const shelfElement = this.viewContainer.createComponent(BoxCaseComponent);

    const componentElement = shelfElement.location.nativeElement
    const tabelShelf= componentElement.querySelector('.warehouse-tree');

    this.renderer.appendChild(tabelShelf, tableFilterContent)
    this.renderer.appendChild(warehouseElement, componentElement)

  }


  reloadData() {
    let type = ''
    let params = {}
    this.route.params.subscribe(param => {
      this.id = +param['id'];
    });
    this.route.queryParams.subscribe(query_param => {
      type = query_param['type'];
    });
    let warehousePathList
    if (this.id){
      this.customshelfService.getWarehousePath(this.id).subscribe(
        (warehouse) => {
          warehousePathList = warehouse;
          // console.log(listFolderPath)
          this.warehousePath = warehousePathList.results
        },)
    }

    params['type__iexact'] = 'Shelf'
    params['parent_warehouse'] = this.id;
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

  goToBoxcase(object,$event){
  //   redict to shelf
    this.router.navigate(['/warehouses',object.id], { queryParams: {type:'Boxcase'} });
    this.renderBoxcase()

  }

  getDeleteMessage(object: Shelf) {
    return $localize`Do you really want to delete the Shelf "${object.name}"?`
  }
  renderWarehouse(){

    const treeWarehouse = document.querySelector('.warehouse-tree');
    const warehouseElement = document.querySelector('.warehouse');
    warehouseElement.innerHTML = ''
    const warehouseRootElement = this.viewContainer.createComponent(WarehouseComponent);

    const componentElement = warehouseRootElement.location.nativeElement
    const treeWarehouseRoot= componentElement.querySelector('.warehouse-tree');
    treeWarehouseRoot.innerHTML = ''
    this.renderer.appendChild(treeWarehouseRoot, treeWarehouse)
    this.renderer.appendChild(warehouseElement, componentElement)

  }
  goToWarehouseRoot(param) {
    this.router.navigate(['/warehouses','root']);
    this.renderWarehouse()

  }


  goToWarehouse(w: Warehouse) {
    this.router.navigate(['/warehouses',w.id], { queryParams: {type:'Warehouse'} });
    this.renderShelf()
  }
}
