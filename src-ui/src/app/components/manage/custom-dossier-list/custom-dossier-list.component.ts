import {
  Directive,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators'
import { first } from 'rxjs'
import {
  MatchingModel,
  MATCHING_ALGORITHMS,
  MATCH_AUTO,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import {
  SortableDirective,
  SortEvent,
} from 'src/app/directives/sortable.directive'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import {
  AbstractNameFilterService,
  BulkEditObjectOperation,
} from 'src/app/services/rest/abstract-name-filter-service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { PermissionsDialogComponent } from '../../common/permissions-dialog/permissions-dialog.component'
import { ShareLink } from 'src/app/data/share-link'
import { environment } from 'src/environments/environment'
import { Router } from '@angular/router'


import { DocumentService } from 'src/app/services/rest/document.service'
import { saveAs } from 'file-saver'
import { NgxBootstrapIconsModule, ColorTheme } from 'ngx-bootstrap-icons';
import { DossierService } from 'src/app/services/rest/dossier.service'
import { Dossier } from 'src/app/data/dossier'
export interface ManagementListColumn {
  key: string

  name: string

  valueFn: any

  rendersHtml?: boolean
}

@Directive()
export abstract class CustomDossierListComponent<T extends ObjectWithId>
  extends ComponentWithPermissions
  implements OnInit, OnDestroy {
  [x: string]: any
  

  constructor(
    private service: AbstractNameFilterService<T>,
    private modalService: NgbModal,
    private editDialogComponent: any,
    private toastService: ToastService,
    private documentListViewService: DocumentListViewService,
    private permissionsService: PermissionsService,
    protected filterRuleType: number,
    public typeName: string,
    public typeNamePlural: string,
    public permissionType: PermissionType,
    public extraColumns: ManagementListColumn[],
    public dossierService: DossierService,
    public isForm: boolean
    
  ) {
    super()
  }

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>
  public id: number
  public data: T[] = []
  displayMode = 'details'
  public page = 1
  private permissionService: PermissionsService
  public collectionSize = 0

  public sortField: string
  public sortReverse: boolean

  public isLoading: boolean = false

  private nameFilterDebounce: Subject<string>
  private unsubscribeNotifier: Subject<any> = new Subject()
  private _nameFilter: string

  public selectedObjects: Set<number> = new Set()
  public togggleAll: boolean = false
  public shareLinks: ShareLink[]
  public dossier: Dossier[] = []
  public dossierPath: Dossier[] = []
  public documentService: DocumentService
  public ColorTheme : ColorTheme
  public canCreate: boolean = false

  ngOnInit(): void {
    if (localStorage.getItem('dossier-list:displayMode') != null) {
      // console.log( localStorage.getItem('dossier-list:displayMode'))
      this.displayMode = localStorage.getItem('dossier-list:displayMode')
    }
    this.reloadData()
    
    this.nameFilterDebounce = new Subject<string>()

    this.nameFilterDebounce
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        debounceTime(400),
        distinctUntilChanged()
      )
      .subscribe((title) => {
        this._nameFilter = title
        this.page = 1
        this.reloadData()
      })
  }

  ngOnDestroy() {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  getMatching(o: MatchingModel) {
    if (o.matching_algorithm == MATCH_AUTO) {
      return $localize`Automatic`
    } else if (o.matching_algorithm == MATCH_NONE) {
      return $localize`None`
    } else if (o.match && o.match.length > 0) {
      return `${MATCHING_ALGORITHMS.find((a) => a.id == o.matching_algorithm).shortName
        }: ${o.match}`
    } else {
      return '-'
    }
  }
  
  // exportToExcelSelected() {
  //   this.awaitingDownload = true
  //   this.dossierService
  //     .bulkExportExcels(
  //       Array.from(this.selectedObjects)
  //     )
  //     .pipe(first())
  //     .subscribe((result: any) => {
  //       saveAs(result, 'download.xlsx')
  //       this.awaitingDownload = false
  //     })
  // }
  
  userCanEditAll(): boolean {
    let canEdit: boolean = this.permissionService.currentUserCan(
      PermissionAction.Change,
      PermissionType.Dossier
    )
    if (!canEdit) return false

    const dossier = this.data.filter((f) => this.selectedObjects.has(f.id))
    canEdit = dossier.every((f) =>
      this.permissionService.currentUserHasObjectPermissions(
        this.PermissionAction.Change,
        f
      )
    )
    return canEdit
  }

  onSort(event: SortEvent) {
    this.sortField = event.column
    this.sortReverse = event.reverse
    this.reloadData()
  }

  reloadData() {
    this.selectedObjects.clear()
    if (this.id){
      let listDossierPath
      this.dossierService.getDossierPath(this.id).subscribe(
        
        (dossier) => {
          listDossierPath = dossier
          // console.log(listDossierPath)
          this.dossierPath = listDossierPath?.results
        },)
      this.dossierService.get(this.id).subscribe(
        (dossier)=>{
          if (dossier?.type=='DOCUMENT') 
            this.canCreate=true
          else{
            this.canCreate=false
          }
        }
      )

    }
    // let listFolderPath 
    // if (this.id){
    //   this.dossierService.getFolderPath(this.id).subscribe(
    //     (dossier) => {
    //       listFolderPath = dossier;
    //       // console.log(listFolderPath)
    //       this.dossier = listFolderPath.results
    //     },)
      
    // }
    // console.log(this.dossier)
    this.isLoading = true
    this.service
      .listDossierFiltered(
        this.page,
        null,
        this.sortField,
        this.sortReverse,
        this.id,
        this._nameFilter,
        true,
        ''
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.data = c.results
        this.collectionSize = c.count
        this.isLoading = false
      })
  }


  openCreateDialog() {
    var activeModal = this.modalService.open(this.editDialogComponent, {
      size:'xl',
      backdrop: 'static',
    })
    activeModal.componentInstance.object = { parent_dossier: this.id }
    activeModal.componentInstance.dialogMode = EditDialogMode.CREATE
    activeModal.componentInstance.succeeded.subscribe(() => {
      this.reloadData()
      this.toastService.showInfo(
        $localize`Successfully created ${this.typeName}.`
      )
    })
    activeModal.componentInstance.failed.subscribe((e) => {
      this.toastService.showError(
        $localize`Error occurred while creating ${this.typeName}.`,
        e
      )
    })
  }
  

  openEditDialog(object: T) {
    var activeModal = this.modalService.open(this.editDialogComponent, {
      size:'xl',
      backdrop: 'static',
    })
    activeModal.componentInstance.object = object
    activeModal.componentInstance.dialogMode = EditDialogMode.EDIT
    activeModal.componentInstance.succeeded.subscribe(() => {
      this.reloadData()
      this.toastService.showInfo(
        $localize`Successfully updated ${this.typeName}.`
      )
    })
    activeModal.componentInstance.failed.subscribe((e) => {
      this.toastService.showError(
        $localize`Error occurred while saving ${this.typeName}.`,
        e
      )
    })
  }

  abstract getDeleteMessage(object: T)

  filterDocuments(object: ObjectWithId) {
    this.documentListViewService.quickFilter([
      { rule_type: this.filterRuleType, value: object.id.toString() },
    ])
  }
  isSelected(object: T){
    return this.selectedObjects.has(object.id)
  }
  saveDisplayMode() {
    localStorage.setItem('dossier-list:displayMode', this.displayMode)
  }

  openDeleteDialog(object: T) {
    // console.log(object)
    var activeModal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    activeModal.componentInstance.title = $localize`Confirm delete`
    activeModal.componentInstance.messageBold = this.getDeleteMessage(object)
    activeModal.componentInstance.message = $localize`Associated documents will not be deleted.`
    activeModal.componentInstance.btnClass = 'btn-danger'
    activeModal.componentInstance.btnCaption = $localize`Delete`
    activeModal.componentInstance.confirmClicked.subscribe(() => {
      activeModal.componentInstance.buttonsEnabled = false
      this.service
        .delete(object)
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe({
          next: () => {
            activeModal.close()
            this.reloadData()
          },
          error: (error) => {
            activeModal.componentInstance.buttonsEnabled = true
            this.toastService.showError(
              $localize`Error while deleting element`,
              error
            )
          },
        })
    })
  }

  get nameFilter() {
    return this._nameFilter
  }

  set nameFilter(nameFilter: string) {
    this.nameFilterDebounce.next(nameFilter)
  }
  trackByDossierId(index, item: Dossier) {
    return item.id
  }
  onNameFilterKeyUp(event: KeyboardEvent) {
    if (event.code == 'Escape') this.nameFilterDebounce.next(null)
  }

  userCanDelete(object: ObjectWithPermissions): boolean {
    return this.permissionsService.currentUserOwnsObject(object)
  }

  userCanEdit(object: ObjectWithPermissions): boolean {
    return this.permissionsService.currentUserHasObjectPermissions(
      this.PermissionAction.Change,
      object
    )
  }

  userCanBulkEdit(action: PermissionAction): boolean {
    if (!this.permissionsService.currentUserCan(action, this.permissionType))
      return false
    let ownsAll: boolean = true
    const objects = this.data.filter((o) => this.selectedObjects.has(o.id))
    ownsAll = objects.every((o) =>
      this.permissionsService.currentUserOwnsObject(o)
    )
    return ownsAll
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedObjects = new Set(this.data.map((o) => o.id))
    } else {
      this.clearSelection()
    }
  }

  clearSelection() {
    this.togggleAll = false
    this.selectedObjects.clear()
  }

  toggleSelected(object) {
    this.selectedObjects.has(object.id)
      ? this.selectedObjects.delete(object.id)
      : this.selectedObjects.add(object.id)
  }
  selectAll(){
    
    this.selectedObjects = new Set(this.data.map((o) => o.id))
  }

  setPermissions() {
    let modal = this.modalService.open(PermissionsDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.confirmClicked.subscribe(
      ({ permissions, merge }) => {
        modal.componentInstance.buttonsEnabled = false
        this.service
          .bulk_edit_objects(
            Array.from(this.selectedObjects),
            BulkEditObjectOperation.SetPermissions,
            permissions,
            merge
          )
          .subscribe({
            next: () => {
              modal.close()
              this.toastService.showInfo(
                $localize`Permissions updated successfully`
              )
              this.reloadData()
            },
            error: (error) => {
              modal.componentInstance.buttonsEnabled = true
              this.toastService.showError(
                $localize`Error updating permissions`,
                error
              )
            },
          })
      }
    )
  }

  delete() {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete all objects.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.service
        .bulk_edit_objects(
          Array.from(this.selectedObjects),
          BulkEditObjectOperation.Delete
        )
        .subscribe({
          next: () => {
            modal.close()
            this.toastService.showInfo($localize`Objects deleted successfully`)
            this.reloadData()
          },
          error: (error) => {
            modal.componentInstance.buttonsEnabled = true
            this.toastService.showError(
              $localize`Error deleting objects`,
              error
            )
          },
        })
    })
  }

}
