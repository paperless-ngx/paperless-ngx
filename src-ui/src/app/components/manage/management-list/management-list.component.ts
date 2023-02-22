import {
  Directive,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
} from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, Subscription } from 'rxjs'
import { debounceTime, distinctUntilChanged } from 'rxjs/operators'
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
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { AbstractNameFilterService } from 'src/app/services/rest/abstract-name-filter-service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

export interface ManagementListColumn {
  key: string

  name: string

  valueFn: any

  rendersHtml?: boolean
}

@Directive()
export abstract class ManagementListComponent<T extends ObjectWithId>
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
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
    public extraColumns: ManagementListColumn[]
  ) {
    super()
  }

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>

  public data: T[] = []

  public page = 1

  public collectionSize = 0

  public sortField: string
  public sortReverse: boolean

  private nameFilterDebounce: Subject<string>
  private subscription: Subscription
  private _nameFilter: string

  ngOnInit(): void {
    this.reloadData()

    this.nameFilterDebounce = new Subject<string>()

    this.subscription = this.nameFilterDebounce
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe((title) => {
        this._nameFilter = title
        this.page = 1
        this.reloadData()
      })
  }

  ngOnDestroy() {
    this.subscription.unsubscribe()
  }

  getMatching(o: MatchingModel) {
    if (o.matching_algorithm == MATCH_AUTO) {
      return $localize`Automatic`
    } else if (o.matching_algorithm == MATCH_NONE) {
      return $localize`None`
    } else if (o.match && o.match.length > 0) {
      return `${
        MATCHING_ALGORITHMS.find((a) => a.id == o.matching_algorithm).shortName
      }: ${o.match}`
    } else {
      return '-'
    }
  }

  onSort(event: SortEvent) {
    this.sortField = event.column
    this.sortReverse = event.reverse
    this.reloadData()
  }

  reloadData() {
    this.service
      .listFiltered(
        this.page,
        null,
        this.sortField,
        this.sortReverse,
        this._nameFilter
      )
      .subscribe((c) => {
        this.data = c.results
        this.collectionSize = c.count
      })
  }

  openCreateDialog() {
    var activeModal = this.modalService.open(this.editDialogComponent, {
      backdrop: 'static',
    })
    activeModal.componentInstance.dialogMode = 'create'
    activeModal.componentInstance.succeeded.subscribe({
      next: () => {
        this.reloadData()
        this.toastService.showInfo(
          $localize`Successfully created ${this.typeName}.`
        )
      },
      error: (e) => {
        this.toastService.showInfo(
          $localize`Error occurred while creating ${
            this.typeName
          } : ${e.toString()}.`
        )
      },
    })
  }

  openEditDialog(object: T) {
    var activeModal = this.modalService.open(this.editDialogComponent, {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = object
    activeModal.componentInstance.dialogMode = 'edit'
    activeModal.componentInstance.succeeded.subscribe({
      next: () => {
        this.reloadData()
        this.toastService.showInfo(
          $localize`Successfully updated ${this.typeName}.`
        )
      },
      error: (e) => {
        this.toastService.showInfo(
          $localize`Error occurred while saving ${
            this.typeName
          } : ${e.toString()}.`
        )
      },
    })
  }

  getDeleteMessage(object: T) {
    return $localize`Do you really want to delete the ${this.typeName}?`
  }

  filterDocuments(object: ObjectWithId) {
    this.documentListViewService.quickFilter([
      { rule_type: this.filterRuleType, value: object.id.toString() },
    ])
  }

  openDeleteDialog(object: T) {
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
      this.service.delete(object).subscribe(
        (_) => {
          activeModal.close()
          this.reloadData()
        },
        (error) => {
          activeModal.componentInstance.buttonsEnabled = true
          this.toastService.showError(
            $localize`Error while deleting element: ${JSON.stringify(
              error.error
            )}`
          )
        }
      )
    })
  }

  get nameFilter() {
    return this._nameFilter
  }

  set nameFilter(nameFilter: string) {
    this.nameFilterDebounce.next(nameFilter)
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
}
