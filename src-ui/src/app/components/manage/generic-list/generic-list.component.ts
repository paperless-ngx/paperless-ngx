import { Directive, OnDestroy, OnInit, QueryList, ViewChildren } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { MatchingModel, MATCHING_ALGORITHMS, MATCH_AUTO } from 'src/app/data/matching-model';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { SortableDirective, SortEvent } from 'src/app/directives/sortable.directive';
import { AbstractNameFilterService } from 'src/app/services/rest/abstract-name-filter-service';
import { ToastService } from 'src/app/services/toast.service';
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component';

@Directive()
export abstract class GenericListComponent<T extends ObjectWithId> implements OnInit, OnDestroy {

  constructor(
    private service: AbstractNameFilterService<T>,
    private modalService: NgbModal,
    private editDialogComponent: any,
    private toastService: ToastService) {
    }

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>;

  public data: T[] = []

  public page = 1

  public collectionSize = 0

  public sortField: string
  public sortReverse: boolean

  private nameFilterDebounce: Subject<string>
  private subscription: Subscription
  private _nameFilter: string

  getMatching(o: MatchingModel) {
    if (o.matching_algorithm == MATCH_AUTO) {
      return $localize`Automatic`
    } else if (o.match && o.match.length > 0) {
      return `${MATCHING_ALGORITHMS.find(a => a.id == o.matching_algorithm).shortName}: ${o.match}`
    } else {
      return "-"
    }
  }

  onSort(event: SortEvent) {
    this.sortField = event.column
    this.sortReverse = event.reverse
    this.reloadData()
  }


  ngOnInit(): void {
    this.reloadData()

    this.nameFilterDebounce = new Subject<string>()

    this.subscription = this.nameFilterDebounce.pipe(
      debounceTime(400),
      distinctUntilChanged()
    ).subscribe(title => {
      this._nameFilter = title
      this.reloadData()
    })
  }

  ngOnDestroy() {
    this.subscription.unsubscribe()
  }

  reloadData() {
    this.service.listFiltered(this.page, null, this.sortField, this.sortReverse, this._nameFilter).subscribe(c => {
      this.data = c.results
      this.collectionSize = c.count
    });
  }

  openCreateDialog() {
    var activeModal = this.modalService.open(this.editDialogComponent, {backdrop: 'static'})
    activeModal.componentInstance.dialogMode = 'create'
    activeModal.componentInstance.success.subscribe(o => {
      this.reloadData()
    })
  }

  openEditDialog(object: T) {
    var activeModal = this.modalService.open(this.editDialogComponent, {backdrop: 'static'})
    activeModal.componentInstance.object = object
    activeModal.componentInstance.dialogMode = 'edit'
    activeModal.componentInstance.success.subscribe(o => {
      this.reloadData()
    })
  }

  getDeleteMessage(object: T) {
    return $localize`Do you really want to delete this element?`
  }

  openDeleteDialog(object: T) {
    var activeModal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    activeModal.componentInstance.title = $localize`Confirm delete`
    activeModal.componentInstance.messageBold = this.getDeleteMessage(object)
    activeModal.componentInstance.message = $localize`Associated documents will not be deleted.`
    activeModal.componentInstance.btnClass = "btn-danger"
    activeModal.componentInstance.btnCaption = $localize`Delete`
    activeModal.componentInstance.confirmClicked.subscribe(() => {
      activeModal.componentInstance.buttonsEnabled = false
      this.service.delete(object).subscribe(_ => {
        activeModal.close()
        this.reloadData()
      }, error => {
        activeModal.componentInstance.buttonsEnabled = true
        this.toastService.showError($localize`Error while deleting element: ${JSON.stringify(error.error)}`)
      })
    }
    )
  }

  get nameFilter() {
    return this._nameFilter
  }

  set nameFilter(nameFilter: string) {
    this.nameFilterDebounce.next(nameFilter)
  }
}
