import { Directive, OnInit } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service';
import { DeleteDialogComponent } from '../../common/delete-dialog/delete-dialog.component';

@Directive()
export abstract class GenericListComponent<T extends ObjectWithId> implements OnInit {
  
  constructor(
    private service: AbstractPaperlessService<T>, 
    private modalService: NgbModal,
    private editDialogComponent: any) {
    }

  public data: T[] = []

  public page = 1

  public collectionSize = 0

  ngOnInit(): void {
    this.reloadData()
  }

  reloadData() {
    this.service.list(this.page).subscribe(c => {
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

  openDeleteDialog(object: T) {
    var activeModal = this.modalService.open(DeleteDialogComponent, {backdrop: 'static'})
    activeModal.componentInstance.message = `Do you really want to delete ${object}?`
    activeModal.componentInstance.message2 = "Associated documents will not be deleted."
    activeModal.componentInstance.deleteClicked.subscribe(() => {
      this.service.delete(object).subscribe(_ => {
        activeModal.close()
        this.reloadData()
      })
    }
    )
  }
}
