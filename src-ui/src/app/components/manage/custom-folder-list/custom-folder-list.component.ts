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
import { Folder } from 'src/app/data/folder'
import { FolderService } from 'src/app/services/rest/folder.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { saveAs } from 'file-saver'
import { Document } from '../../../data/document'
export interface ManagementListColumn {
  key: string

  name: string

  valueFn: any

  rendersHtml?: boolean
}

@Directive()
export abstract class CustomFolderListComponent<T extends ObjectWithId>
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
    public folderService: FolderService,

  ) {
    super()
  }

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>
  public id: number
  public data: T[] = []
  documents: Document[] = []
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
  public folderPath: Folder[] = []
  public documentService: DocumentService
  public folderCut: number[] = []
  public isFolderCutClicked = false;
  public preFolder: number = null;


  ngOnInit(): void {
    if (localStorage.getItem('folder-list:displayMode') != null) {
      this.displayMode = localStorage.getItem('folder-list:displayMode')
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
  getSelectedObjects() {
    return this.selectedObjects
  }
  exportToExcelSelected() {
    this.awaitingDownload = true
    this.folderService
      .bulkExportExcels(
        Array.from(this.selectedObjects)
      )
      .pipe(first())
      .subscribe((result: any) => {
        saveAs(result, 'download.xlsx')
        this.awaitingDownload = false
      })
  }

  userCanEditAll(): boolean {
    let canEdit: boolean = this.permissionService.currentUserCan(
      PermissionAction.Change,
      PermissionType.Folder
    )
    if (!canEdit) return false

    const folder = this.data.filter((f) => this.selectedObjects.has(f.id))
    canEdit = folder.every((f) =>
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

  extractDocuments(){}

  reloadData() {
    if (this.id!=this.preFolder)
      this.page=1
    this.selectedObjects.clear()
    let listFolderPath
    if (this.id){
      this.folderService.getFolderPath(this.id).subscribe(
        (folder) => {
          listFolderPath = folder;
          // console.log(listFolderPath)
          this.folderPath = listFolderPath.results
        },)
    }
    // console.log(this.folderPath)
    this.isLoading = true
    this.service
      .listFolderFiltered(
        this.page,
        null,
        this.sortField,
        this.sortReverse,
        this.id,
        this._nameFilter,
        true
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((c) => {
        this.data = c.results
        this.extractDocuments()
        this.collectionSize = c.count
        this.isLoading = false
      })

    this.preFolder=this.id
  }


  openCreateDialog() {
    var activeModal = this.modalService.open(this.editDialogComponent, {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = { parent_folder: this.id }
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
    localStorage.setItem('folder-list:displayMode', this.displayMode)
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
  trackByFolderId(index, item: Folder) {
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
          .bulk_edit_folders(
            Array.from(this.selectedObjects),
            null,
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
        .bulk_edit_folders(
          Array.from(this.selectedObjects),
          null,
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

  cutFolder() {
    this.folderCut = Array.from(this.selectedObjects)
    this.isFolderCutClicked = true;
    return this.folderCut
  }

  cancelFolder() {
    this.reloadData()
    this.folderCut=[]
    // const currentUrl = this.router.url;
    //
    //
    // const newUrl = currentUrl.split('?')[0]; // Lấy phần trước dấu hỏi
    // this.router.navigateByUrl(newUrl);
    this.isFolderCutClicked=false
    if (this.router.url.includes('/folders/')) {
      this.id = this.route.snapshot.params['id'];
      this.router.navigate(['/folders/', this.id], {
        queryParams: {}
      });
    }

    else {
      this.router.navigate(['/folders/root'], {
        queryParams: {}
      });
    }
  }
  getCutFolder(){
    let folderIds
    this.route.queryParams.subscribe(params => {
      folderIds = params['folderIds'];
    });

    const parts = folderIds.split(',');
    this.folderCut = parts.map(part => parseInt(part, 10));
    return this.folderCut
  }




  update() {
    this.id = this.route.snapshot.params['id']
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm update`
    modal.componentInstance.messageBold = $localize`This operation will permanently update all objects.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    this.folderCut=[];
    this.isFolderCutClicked=false
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.service
        .bulk_edit_folders(
          Array.from(this.getCutFolder()),
          Number(this.id),
          BulkEditObjectOperation.Update
        )
        .subscribe({
          next: () => {
            modal.close()
            this.toastService.showInfo($localize`Objects update successfully`)
            this.reloadData()

            if (this.router.url.includes('/folders/')) {
              this.router.navigate(['/folders/', this.id], {
                queryParams: {}
              });
            }
            else {
              this.router.navigate(['/folders/root'], {
                queryParams: {}
              });
            }

          },
          error: (error) => {
            modal.componentInstance.buttonsEnabled = true
            this.toastService.showError(
              $localize`Error updating objects`,
              error
            )
          },
        })
    })
  }

}
