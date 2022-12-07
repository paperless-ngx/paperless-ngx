import { Directive, EventEmitter, Input, OnInit, Output } from '@angular/core'
import { FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { Observable } from 'rxjs'
import { MATCHING_ALGORITHMS, MATCH_AUTO } from 'src/app/data/matching-model'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service'

@Directive()
export abstract class EditDialogComponent<
  T extends ObjectWithPermissions | ObjectWithId
> implements OnInit
{
  constructor(
    private service: AbstractPaperlessService<T>,
    private activeModal: NgbActiveModal
  ) {}

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
      if (this.object['permissions']) {
        this.object['set_permissions'] = {
          view: (this.object as ObjectWithPermissions).permissions
            .filter((p) => (p[1] as string).includes('view'))
            .map((p) => p[0]),
          change: (this.object as ObjectWithPermissions).permissions
            .filter((p) => (p[1] as string).includes('change'))
            .map((p) => p[0]),
        }
      }
      this.objectForm.patchValue(this.object)
    }

    // wait to enable close button so it doesnt steal focus from input since its the first clickable element in the DOM
    setTimeout(() => {
      this.closeEnabled = true
    })
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
        break
    }
  }

  getMatchingAlgorithms() {
    return MATCHING_ALGORITHMS
  }

  get patternRequired(): boolean {
    return this.objectForm?.value.matching_algorithm !== MATCH_AUTO
  }

  save() {
    var newObject = Object.assign(
      Object.assign({}, this.object),
      this.objectForm.value
    )
    var serverResponse: Observable<T>
    switch (this.dialogMode) {
      case 'create':
        serverResponse = this.service.create(newObject)
        break
      case 'edit':
        serverResponse = this.service.update(newObject)
      default:
        break
    }
    this.networkActive = true
    serverResponse.subscribe({
      next: (result) => {
        this.activeModal.close()
        this.success.emit(result)
      },
      error: (error) => {
        this.error = error.error
        this.networkActive = false
      },
    })
  }

  cancel() {
    this.activeModal.close()
  }
}
