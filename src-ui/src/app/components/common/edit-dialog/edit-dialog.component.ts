import { Directive, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { MATCHING_ALGORITHMS, MATCH_AUTO } from 'src/app/data/matching-model';
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

  networkActive = false

  closeEnabled = false

  error = null

  abstract getForm(): FormGroup

  objectForm: FormGroup = this.getForm()

  ngOnInit(): void {
    if (this.object != null) {
      this.objectForm.patchValue(this.object)
    }

    // wait to enable close button so it doesnt steal focus from input since its the first clickable element in the DOM
    setTimeout(() => {
      this.closeEnabled = true
    });
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

  get patternRequired(): boolean {
    return this.objectForm?.value.matching_algorithm !== MATCH_AUTO
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
    this.networkActive = true
    serverResponse.subscribe(result => {
      this.activeModal.close()
      this.success.emit(result)
    }, error => {
      this.error = error.error
      this.networkActive = false
    })
  }

  cancel() {
    this.activeModal.close()
  }
}
