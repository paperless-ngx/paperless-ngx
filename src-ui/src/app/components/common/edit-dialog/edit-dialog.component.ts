import { Directive, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';
import { MATCHING_ALGORITHMS } from 'src/app/data/matching-model';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service';
import { ToastService } from 'src/app/services/toast.service';

@Directive()
export abstract class EditDialogComponent<T extends ObjectWithId> implements OnInit {

  constructor(
    private service: AbstractPaperlessService<T>,
    private activeModal: NgbActiveModal,
    private toastService: ToastService) { }

  @Input()
  dialogMode: string = 'create'

  @Input()
  object: T

  @Output()
  success = new EventEmitter()

  abstract getForm(): FormGroup

  objectForm: FormGroup = this.getForm()

  ngOnInit(): void {
    if (this.object != null) {
      this.objectForm.patchValue(this.object)
    }
  }

  getCreateTitle() {
    return $localize`Create new item`
  }

  getEditTitle() {
    return $localize`Edit item`
  }

  getSaveErrorMessage(error: string) {
    return $localize`Could not save element: ${error}`
  }

  getTitle() {
    switch (this.dialogMode) {
      case 'create':
        return this.getCreateTitle()
      case 'edit':
        return this.getEditTitle()
      default:
        break;
    }
  }

  getMatchingAlgorithms() {
    return MATCHING_ALGORITHMS
  }

  save() {
    var newObject = Object.assign(Object.assign({}, this.object), this.objectForm.value)
    var serverResponse: Observable<T>
    switch (this.dialogMode) {
      case 'create':
        serverResponse = this.service.create(newObject)
        break;
      case 'edit':
        serverResponse = this.service.update(newObject)
      default:
        break;
    }
    serverResponse.subscribe(result => {
      this.activeModal.close()
      this.success.emit(result)
    }, error => {
      this.toastService.showError(this.getSaveErrorMessage(error.error.name))
    })
  }

  cancel() {
    this.activeModal.close()
  }
}
