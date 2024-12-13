import { Directive, EventEmitter, Input, OnInit, Output } from '@angular/core'
import { FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { Observable } from 'rxjs'
import {
  MATCHING_ALGORITHMS,
  MATCH_AUTO,
  MATCH_NONE,
} from 'src/app/data/matching-model'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { User } from 'src/app/data/user'
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { PermissionsFormObject } from '../input/permissions/permissions-form/permissions-form.component'

export enum EditDialogMode {
  CREATE = 0,
  EDIT = 1,
}

@Directive()
export abstract class EditDialogComponent<
    T extends ObjectWithPermissions | ObjectWithId,
  >
  extends LoadingComponentWithPermissions
  implements OnInit
{
  constructor(
    protected service: AbstractPaperlessService<T>,
    private activeModal: NgbActiveModal,
    private userService: UserService,
    private settingsService: SettingsService
  ) {
    super()
  }

  users: User[]

  @Input()
  dialogMode: EditDialogMode = EditDialogMode.CREATE

  @Input()
  object: T

  @Output()
  succeeded = new EventEmitter()

  @Output()
  failed = new EventEmitter()

  networkActive = false

  closeEnabled = false

  error = null

  abstract getForm(): FormGroup

  objectForm: FormGroup = this.getForm()

  ngOnInit(): void {
    if (this.object != null && this.dialogMode !== EditDialogMode.CREATE) {
      if ((this.object as ObjectWithPermissions).permissions) {
        this.object['set_permissions'] = this.object['permissions']
      }

      this.object['permissions_form'] = {
        owner: (this.object as ObjectWithPermissions).owner,
        set_permissions: (this.object as ObjectWithPermissions).permissions,
      }
      this.objectForm.patchValue(this.object)
    } else {
      // e.g. if name was set
      this.objectForm.patchValue(this.object)
      // defaults from settings
      this.objectForm.patchValue({
        permissions_form: {
          owner: this.settingsService.get(SETTINGS_KEYS.DEFAULT_PERMS_OWNER),
          set_permissions: {
            view: {
              users: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS
              ),
              groups: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS
              ),
            },
            change: {
              users: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS
              ),
              groups: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS
              ),
            },
          },
        },
      })
    }

    // wait to enable close button so it doesn't steal focus from input since its the first clickable element in the DOM
    setTimeout(() => {
      this.closeEnabled = true
    })

    this.userService.listAll().subscribe((r) => {
      this.users = r.results
    })
  }

  getCreateTitle() {
    return $localize`Create new item`
  }

  getEditTitle() {
    return $localize`Edit item`
  }

  getTitle() {
    switch (this.dialogMode) {
      case EditDialogMode.CREATE:
        return this.getCreateTitle()
      case EditDialogMode.EDIT:
        return this.getEditTitle()
      default:
        break
    }
  }

  getMatchingAlgorithms() {
    return MATCHING_ALGORITHMS
  }

  get patternRequired(): boolean {
    return (
      this.objectForm?.value.matching_algorithm !== MATCH_AUTO &&
      this.objectForm?.value.matching_algorithm !== MATCH_NONE
    )
  }

  save() {
    this.error = null
    const formValues = Object.assign({}, this.objectForm.value)
    const permissionsObject: PermissionsFormObject =
      this.objectForm.get('permissions_form')?.value
    if (permissionsObject) {
      formValues.owner = permissionsObject.owner
      formValues.set_permissions = permissionsObject.set_permissions
      delete formValues.permissions_form
    }

    var newObject = Object.assign(Object.assign({}, this.object), formValues)
    var serverResponse: Observable<T>
    switch (this.dialogMode) {
      case EditDialogMode.CREATE:
        serverResponse = this.service.create(newObject)
        break
      case EditDialogMode.EDIT:
        serverResponse = this.service.update(newObject)
      default:
        break
    }
    this.networkActive = true
    serverResponse.subscribe({
      next: (result) => {
        this.activeModal.close()
        this.succeeded.emit(result)
      },
      error: (error) => {
        this.error = error.error
        this.networkActive = false
        this.failed.next(error)
      },
    })
  }

  cancel() {
    this.activeModal.close()
  }
}
