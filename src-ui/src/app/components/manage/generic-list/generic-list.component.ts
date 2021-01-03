import { Directive, OnInit, QueryList, ViewChildren } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { MatchingModel, MATCHING_ALGORITHMS, MATCH_AUTO } from 'src/app/data/matching-model';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { SortableDirective, SortEvent } from 'src/app/directives/sortable.directive';
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service';
import { ToastService } from 'src/app/services/toast.service';
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component';

@Directive()
export abstract class GenericListComponent<T extends ObjectWithId> implements OnInit {

  constructor(
    private service: AbstractPaperlessService<T>,
    private modalService: NgbModal,
    private editDialogComponent: any,
    private toastService: ToastService) {
    }

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>;

  public data: T[] = []

  public page = 1

  public collectionSize = 0

  public sortField: string
  public sortDirection: string

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

    if (event.direction && event.direction.length > 0) {
      this.sortField = event.column
      this.sortDirection = event.direction
    } else {
      this.sortField = null
      this.sortDirection = null
    }

    this.headers.forEach(header => {
      if (header.sortable !== this.sortField) {
        header.direction = '';
      }
    });

    this.reloadData()
  }

  ngOnInit(): void {
    this.reloadData()
  }

  reloadData() {
    // TODO: this is a hack
    this.service.list(this.page, null, this.sortField, this.sortDirection == 'des').subscribe(c => {
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
}
