import { Component, Renderer2, ViewChild, ViewContainerRef } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Router } from '@angular/router'
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
import { ActivatedRoute } from '@angular/router'
import { EditCustomShelfdMode } from '../../common/edit-dialog/edit-customshelf/edit-customshelf.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators'
import { Subject } from 'rxjs'
import { ShelfComponent } from '../shelf/shelf.component'
import { BoxCaseComponent } from '../boxcase/boxcase.component'

@Component({
  selector: 'pngx-warehouse',
  templateUrl: './warehouse.component.html',
  styleUrls: ['./warehouse.component.scss']
})
export class WarehouseComponent extends ManagementListComponent<Warehouse> {
  @ViewChild('warehouseTree', { read: ViewContainerRef }) container!: ViewContainerRef
  public warehousePath: Warehouse[] = []
  constructor(
    warehouseService: WarehouseService,
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

  openCreateDialog() {
    var activeModal = this.getModalService().open(this.getEditDialogComponent(), {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = { parent_warehouse: this.id,type: 'Warehouse' }
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
  reloadData() {
    let type = ''
    this.route.params.subscribe(params => {
      this.id = +params['id'];
    });
    this.route.queryParams.subscribe(params => {
      type = params['type'];
    });
    if (this.id! && type =='Shelf'){
       this.router.navigate(['/warehouses',this.id], { queryParams: {type:'Shelf'} });
       this.renderShelf()
        return;
    }else if (this.id! && type =='Boxcase'){
       this.router.navigate(['/warehouses',this.id], { queryParams: {type:'Boxcase'} });
       this.renderBoxcase()
       return;
    }
    let warehousePathList
    if (this.id){
        this.warehouseService.getWarehousePath(this.id).subscribe(
        (warehouse) => {
          warehousePathList = warehouse;
          // console.log(listFolderPath)
          this.warehousePath = warehousePathList.results
        },)
    }

    let params = {}
    params['type__iexact'] = 'Warehouse'
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

  getDeleteMessage(object: Warehouse) {
    return $localize`Do you really want to delete the warehouse "${object.name}"?`
  }

  renderWarehouse(){

    const tableFilterContent = document.querySelector('.warehouse-tree');
    const warehouseElement = document.querySelector('.warehouse');
    warehouseElement.innerHTML = ''
    const shelfElement = this.viewContainer.createComponent(WarehouseComponent);

    const componentElement = shelfElement.location.nativeElement
    const tabelShelf= componentElement.querySelector('.warehouse-tree');

    this.renderer.appendChild(tabelShelf, tableFilterContent)
    this.renderer.appendChild(warehouseElement, componentElement)

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

  renderShelf(){

    const tableFilterContent = document.querySelector('.warehouse-tree');
    const warehouseElement = document.querySelector('.warehouse');
    warehouseElement.innerHTML = ''
    const shelfElement = this.viewContainer.createComponent(ShelfComponent);

    const componentElement = shelfElement.location.nativeElement
    const tabelShelf= componentElement.querySelector('.warehouse-tree');

    this.renderer.appendChild(tabelShelf, tableFilterContent)
    this.renderer.appendChild(warehouseElement, componentElement)

  }
  goToShelfBoxcase(object){
    if (object.type === 'Warehouse'){
      this.goToShelf(object)
    }if (object.type === 'Shelf'){
      this.goToBoxcase(object)
    }

  }

  goToShelf(object){
    this.router.navigate(['/warehouses',object.id], { queryParams: {type:'Shelf'} });
    this.renderShelf()
  }
  goToBoxcase(object){
    this.router.navigate(['/warehouses',object.id], { queryParams: {type:'Boxcase'} });
    this.renderBoxcase()
  }


}
