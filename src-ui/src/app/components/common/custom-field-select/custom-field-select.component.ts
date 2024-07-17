import { Component, forwardRef, Input, OnInit } from '@angular/core'
import {
  AbstractControl,
  ControlValueAccessor,
  FormControl,
  FormGroup,
  NG_VALUE_ACCESSOR,
} from '@angular/forms'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { Subject, first, takeUntil } from 'rxjs'
@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CustomFieldSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-custom-field-select',
  templateUrl: './custom-field-select.component.html',
  styleUrls: ['./custom-field-select.component.scss'],
})
export class CustomFieldSelectComponent
  extends ComponentWithPermissions
  implements OnInit, ControlValueAccessor
{
  public  customFields: CustomField[]=[]
  @Input()
  title: string = 'Custom field'

  @Input()
  error: string

  private unsubscribeNotifier: Subject<any> = new Subject()
  public unusedFields: CustomField[]
  permissions: string[]
  dataContainCustomFields: []=[]
  dictCustomFieldsEnable: {}={}
  form = new FormGroup({})

  typesWithAllActions: Set<string> = new Set()

  _inheritedPermissions: string[] = []
  _inheritedCustomFields: CustomField[] = []

  @Input()
  set inheritedPermissions(inherited: string[]) {
    // remove <app_label>. from permission strings
    const newInheritedPermissions = inherited?.length
      ? inherited.map((p) => p.replace(/^\w+\./g, ''))
      : []

    if (this._inheritedPermissions !== newInheritedPermissions) {
      this._inheritedPermissions = newInheritedPermissions
      this.writeValue(this.permissions) // updates visual checks etc.
    }

    this.updateDisabledStates()
  }
  @Input()
  set inheritedCustomFields(inherited: CustomField[]) {
    // this.getFields()
    // remove <app_label>. from permission strings
    const newInheritedCustomFields = inherited?.length
    ? inherited
    : []
    

    if (this._inheritedCustomFields !== newInheritedCustomFields) {
      this._inheritedCustomFields = newInheritedCustomFields
      console.log(this.customFields)
      this.writeValueCustomField(this.customFields) // updates visual checks etc.
    }

    this.updateDisabledStates()
  }

  inheritedWarning: string = $localize`Inherited from dossier`

  constructor(
    private readonly permissionsService: PermissionsService, 
    private customFieldsService: CustomFieldsService) {
    super()
    
    for (const type in PermissionType) {
      const control = new FormGroup({})
      for (const action in PermissionAction) {
        control.addControl(action, new FormControl(null))
      }
      this.form.addControl(type, control)
    }
  }


  writeValue(permissions: string[]): void {
    if (this.permissions === permissions) {
      return
    }

    this.permissions = permissions ?? []
    const allPerms = this._inheritedPermissions.concat(this.permissions)

    allPerms.forEach((permissionStr) => {
      const { actionKey, typeKey } =
        this.permissionsService.getPermissionKeys(permissionStr)

      if (actionKey && typeKey) {
        if (this.form.get(typeKey)?.get(actionKey)) {
          this.form
            .get(typeKey)
            .get(actionKey)
            .patchValue(true, { emitEvent: false })
        }
      }
    })
    Object.keys(PermissionType).forEach((type) => {
      if (
        Object.values(this.form.get(type).value).every((val) => val == true)
      ) {
        this.typesWithAllActions.add(type)
      } else {
        this.typesWithAllActions.delete(type)
      }
    })

    this.updateDisabledStates()
  }

  writeValueCustomField(customFields: CustomField[]): void {
    if (this.customFields === customFields) {
      return
    }


    this.customFields = customFields ?? []
    this._inheritedCustomFields.push(...this.customFields)

    
    this.updateDisabledStates()
  }

  onChange = (newValue: string[]) => {}

  onTouched = () => {}

  disabled: boolean = false

  registerOnChange(fn: any): void {
    this.onChange = fn
  }

  registerOnTouched(fn: any): void {
    this.onTouched = fn
  }

  setDisabledState?(isDisabled: boolean): void {
    this.disabled = isDisabled
  }

  ngOnInit(): void {
    this.form.valueChanges.subscribe((newValue) => {
      let permissions = []
      let custom_fields = []

      Object.entries(newValue).forEach(([typeKey, typeValue]) => {
        // e.g. [Document, { Add: true, View: true ... }]
        const selectedActions = Object.entries(typeValue).filter(
          ([actionKey, actionValue]) => actionValue == true
        )

        selectedActions.forEach(([actionKey, actionValue]) => {
          permissions.push(
            (PermissionType[typeKey] as string).replace(
              '%s',
              PermissionAction[actionKey]
            )
          )
        })

        if (selectedActions.length == Object.entries(typeValue).length) {
          this.typesWithAllActions.add(typeKey)
        } else {
          this.typesWithAllActions.delete(typeKey)
        }
      })

      this.onChange(
        permissions.filter((p) => !this._inheritedPermissions.includes(p))
      )
    })
  }

  toggleAll(event, type) {
    const typeGroup = this.form.get(type)
    if (event.target.checked) {
      Object.keys(PermissionAction).forEach((action) => {
        typeGroup.get(action).patchValue(true)
      })
      this.typesWithAllActions.add(type)
    } else {
      Object.keys(PermissionAction).forEach((action) => {
        typeGroup.get(action).patchValue(false)
      })
      this.typesWithAllActions.delete(type)
    }
  }

  isInherited(typeKey: string, actionKey: string = null) {
    if (this._inheritedPermissions.length == 0) return false
    else if (actionKey) {
      return this._inheritedPermissions.includes(
        this.permissionsService.getPermissionCode(
          PermissionAction[actionKey],
          PermissionType[typeKey]
        )
      )
    } else {
      return Object.values(PermissionAction).every((action) => {
        return this._inheritedPermissions.includes(
          this.permissionsService.getPermissionCode(
            action as PermissionAction,
            PermissionType[typeKey]
          )
        )
      })
    }
  }

  updateDisabledStates() {
    for (const type in PermissionType) {
      const control = this.form.get(type)
      let actionControl: AbstractControl
      for (const action in PermissionAction) {
        actionControl = control.get(action)
        this.isInherited(type, action) || this.disabled
          ? actionControl.disable()
          : actionControl.enable()
      }
    }
  }
}
