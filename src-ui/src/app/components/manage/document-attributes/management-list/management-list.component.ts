import { HttpErrorResponse } from '@angular/common/http'
import {
  Directive,
  inject,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
} from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject } from 'rxjs'
import {
  debounceTime,
  delay,
  distinctUntilChanged,
  takeUntil,
  tap,
} from 'rxjs/operators'
import { ConfirmDialogComponent } from 'src/app/components/common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { PermissionsDialogComponent } from 'src/app/components/common/permissions-dialog/permissions-dialog.component'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'
import {
  MATCH_AUTO,
  MATCH_NONE,
  MATCHING_ALGORITHMS,
  MatchingModel,
} from 'src/app/data/matching-model'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
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
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'

export interface ManagementListColumn {
  key: string

  name: string

  valueFn?: any

  badgeFn?: (object: any) => {
    text: string
    textColor?: string
    backgroundColor?: string
  }

  hideOnMobile?: boolean

  monospace?: boolean
}

@Directive()
export abstract class ManagementListComponent<T extends MatchingModel>
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  protected service: AbstractNameFilterService<T>
  private readonly modalService: NgbModal = inject(NgbModal)
  protected editDialogComponent: any
  private readonly toastService: ToastService = inject(ToastService)
  private readonly documentListViewService: DocumentListViewService = inject(
    DocumentListViewService
  )
  private readonly permissionsService: PermissionsService =
    inject(PermissionsService)
  protected filterRuleType: number
  public typeName: string
  public typeNamePlural: string
  public permissionType: PermissionType
  public extraColumns: ManagementListColumn[]

  private readonly settingsService = inject(SettingsService)

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>

  public data: T[] = []
  private unfilteredData: T[] = []
  private allIDs: number[] = []

  public page = 1

  public collectionSize = 0

  public sortField: string
  public sortReverse: boolean

  private nameFilterDebounce: Subject<string>
  protected unsubscribeNotifier: Subject<any> = new Subject()
  protected _nameFilter: string

  public selectedObjects: Set<number> = new Set()
  public togggleAll: boolean = false

  ngOnInit(): void {
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

  protected filterData(data: T[]): T[] {
    return data
  }

  getDocumentCount(object: MatchingModel): number {
    return (
      object.document_count ??
      this.unfilteredData.find((d) => d.id == object.id)?.document_count ??
      0
    )
  }

  public getOriginalObject(object: T): T {
    return this.unfilteredData.find((d) => d?.id == object?.id) || object
  }

  reloadData(extraParams: { [key: string]: any } = null) {
    this.loading = true
    this.clearSelection()
    this.service
      .listFiltered(
        this.page,
        this.pageSize,
        this.sortField,
        this.sortReverse,
        this._nameFilter,
        true,
        extraParams
      )
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        tap((c) => {
          this.unfilteredData = c.results
          this.data = this.filterData(c.results)
          this.collectionSize = c.all?.length ?? c.count
          this.allIDs = c.all
        }),
        delay(100)
      )
      .subscribe({
        error: (error: HttpErrorResponse) => {
          if (error.error?.detail?.includes('Invalid page')) {
            this.page = 1
            this.reloadData()
          }
        },
        next: () => {
          this.show = true
          this.loading = false
        },
      })
  }

  openCreateDialog() {
    const activeModal = this.modalService.open(this.editDialogComponent, {
      backdrop: 'static',
    })
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
    const activeModal = this.modalService.open(this.editDialogComponent, {
      backdrop: 'static',
    })
    activeModal.componentInstance.object = object
    activeModal.componentInstance.dialogMode = EditDialogMode.EDIT
    activeModal.componentInstance.succeeded.subscribe(() => {
      this.reloadData()
      this.toastService.showInfo(
        $localize`Successfully updated ${this.typeName} "${object.name}".`
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

  getDocumentFilterUrl(object: MatchingModel) {
    return this.documentListViewService.getQuickFilterUrl([
      { rule_type: this.filterRuleType, value: object.id.toString() },
    ])
  }

  openDeleteDialog(object: T) {
    const activeModal = this.modalService.open(ConfirmDialogComponent, {
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

  onNameFilterKeyUp(event: KeyboardEvent) {
    if (event.code == 'Escape') this.nameFilterDebounce.next(null)
  }

  public get pageSize(): number {
    return (
      this.settingsService.get(SETTINGS_KEYS.OBJECT_LIST_SIZES)[
        this.typeNamePlural
      ] || 25
    )
  }

  public set pageSize(newPageSize: number) {
    this.settingsService.set(SETTINGS_KEYS.OBJECT_LIST_SIZES, {
      ...this.settingsService.get(SETTINGS_KEYS.OBJECT_LIST_SIZES),
      [this.typeNamePlural]: newPageSize,
    })
    this.settingsService.storeSettings().subscribe({
      next: () => {
        this.page = 1
        this.reloadData()
      },
      error: (error) => {
        this.toastService.showError($localize`Error saving settings`, error)
      },
    })
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

  protected getSelectableIDs(objects: T[]): number[] {
    return objects.map((o) => o.id)
  }

  clearSelection() {
    this.togggleAll = false
    this.selectedObjects.clear()
  }

  selectNone() {
    this.clearSelection()
  }

  selectPage() {
    this.selectedObjects = new Set(this.getSelectableIDs(this.data))
    this.togggleAll = this.areAllPageItemsSelected()
  }

  selectAll() {
    if (!this.collectionSize) {
      this.clearSelection()
      return
    }
    this.selectedObjects = new Set(this.allIDs)
    this.togggleAll = this.areAllPageItemsSelected()
  }

  toggleSelected(object) {
    this.selectedObjects.has(object.id)
      ? this.selectedObjects.delete(object.id)
      : this.selectedObjects.add(object.id)
    this.togggleAll = this.areAllPageItemsSelected()
  }

  protected areAllPageItemsSelected(): boolean {
    const ids = this.getSelectableIDs(this.data)
    return ids.length > 0 && ids.every((id) => this.selectedObjects.has(id))
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
    modal.componentInstance.messageBold = $localize`This operation will permanently delete the selected ${this.typeNamePlural}.`
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
