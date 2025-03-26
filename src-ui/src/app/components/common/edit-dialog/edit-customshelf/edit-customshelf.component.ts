
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
import { User } from 'src/app/data/user'
import { AbstractEdocService } from 'src/app/services/rest/abstract-edoc-service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { PermissionsFormObject } from '../../input/permissions/permissions-form/permissions-form.component'
import { EditDialogMode } from '../edit-dialog.component'
import { getCheckerboard } from 'ngx-color'

export enum EditCustomShelfdMode {
  CREATE = 0,
  EDIT = 1,
}

@Directive()
export abstract class EditCustomShelfComponent<
  T extends ObjectWithPermissions | ObjectWithId,
> implements OnInit {
  [x: string]: any
  constructor(
    protected service: AbstractEdocService<T>,
    private activeModal: NgbActiveModal,
    private userService: UserService,
    private settingsService: SettingsService
  ) { }

  users: User[]

  @Input()
  dialogMode: EditCustomShelfdMode = EditCustomShelfdMode.CREATE

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
    // console.log(this.object)
    this.loadWarehouses();
    if (this.object != null && this.dialogMode !== EditCustomShelfdMode.CREATE) {
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


  getCheckCreate() {
    if (this.dialogMode == EditCustomShelfdMode.CREATE) {
      return false;
    }
    else {
      return true;
    }
  }

  getCreateTitle() {
    return $localize`Create new item`
  }

  getEditTitle() {
    return $localize`Edit item`
  }

  getTitle() {
    switch (this.dialogMode) {
      case EditCustomShelfdMode.CREATE:
        return this.getCreateTitle()
      case EditCustomShelfdMode.EDIT:
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
      case EditCustomShelfdMode.CREATE:
        newObject.parent_warehouse = this.object['parent_warehouse'];
        // console.log(newObject);
        serverResponse = this.service.create(newObject)
        break
      case EditCustomShelfdMode.EDIT:
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
