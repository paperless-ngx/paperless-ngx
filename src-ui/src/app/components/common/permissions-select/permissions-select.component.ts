import { KeyValue, KeyValuePipe } from '@angular/common'
import { Component, forwardRef, inject, Input, OnInit } from '@angular/core'
import {
  AbstractControl,
  ControlValueAccessor,
  FormControl,
  FormGroup,
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsSelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-permissions-select',
  templateUrl: './permissions-select.component.html',
  styleUrls: ['./permissions-select.component.scss'],
  imports: [
    KeyValuePipe,
    NgxBootstrapIconsModule,
    NgbPopoverModule,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class PermissionsSelectComponent
  extends ComponentWithPermissions
  implements OnInit, ControlValueAccessor
{
  private readonly permissionsService = inject(PermissionsService)
  private readonly settingsService = inject(SettingsService)

  @Input()
  title: string = 'Permissions'

  @Input()
  error: string

  permissions: string[]

  form = new FormGroup({})

  typesWithAllActions: Set<string> = new Set()

  private readonly actionOrder = [
    PermissionAction.Add,
    PermissionAction.Change,
    PermissionAction.Delete,
    PermissionAction.View,
  ]

  _inheritedPermissions: string[] = []

  @Input()
  set inheritedPermissions(inherited: string[]) {
    // remove <app_label>. from permission strings
    const newInheritedPermissions = inherited?.length
      ? inherited.map((p) => p.replace(/^\w+\./g, ''))
      : []

    const changed =
      newInheritedPermissions.length !== this._inheritedPermissions.length ||
      newInheritedPermissions.some(
        (p) => !this._inheritedPermissions.includes(p)
      )

    if (changed) {
      // skip inherited permissions, these are the explicitly set ones
      this.permissions = this.getSelectedPermissions(
        this.form.getRawValue()
      ).filter((p) => !this._inheritedPermissions.includes(p))
      this._inheritedPermissions = newInheritedPermissions
      this.applyCheckedState()
    } else {
      this.updateDisabledStates()
    }
  }

  inheritedWarning: string = $localize`Inherited from group`

  public allowedTypes = Object.keys(PermissionType)

  constructor() {
    super()
    if (!this.settingsService.get(SETTINGS_KEYS.AUDITLOG_ENABLED)) {
      this.allowedTypes.splice(this.allowedTypes.indexOf('History'), 1)
    }
    this.allowedTypes.forEach((type) => {
      const control = new FormGroup({})
      for (const action of Object.keys(PermissionAction)) {
        control.addControl(action, new FormControl(null))
      }
      this.form.addControl(type, control)
    })
  }

  writeValue(permissions: string[]): void {
    if (this.permissions === permissions) {
      return
    }

    this.permissions = permissions ?? []
    this.applyCheckedState()
  }

  // sets every checkbox from inherited + own perms
  private applyCheckedState(): void {
    const allPerms = this._inheritedPermissions.concat(this.permissions)

    this.allowedTypes.forEach((type) => {
      const typeGroup = this.form.get(type)
      for (const action of Object.keys(PermissionAction)) {
        typeGroup.get(action)?.patchValue(
          allPerms.includes(
            this.permissionsService.getPermissionCode(
              PermissionAction[action],
              PermissionType[type]
            )
          ),
          { emitEvent: false } // don't trigger valueChanges now
        )
      }

      if (this.typeHasAllActionsSelected(type)) {
        this.typesWithAllActions.add(type)
      } else {
        this.typesWithAllActions.delete(type)
      }
    })

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
      const permissions = this.getSelectedPermissions(newValue)

      Object.keys(newValue).forEach((typeKey) => {
        if (this.typeHasAllActionsSelected(typeKey)) {
          this.typesWithAllActions.add(typeKey)
        } else {
          this.typesWithAllActions.delete(typeKey)
        }
      })

      this.onChange(
        permissions.filter((p) => !this._inheritedPermissions.includes(p))
      )
    })

    this.updateDisabledStates()
  }

  toggleAll(event, type) {
    const typeGroup = this.form.get(type)
    Object.keys(PermissionAction)
      .filter((action) =>
        this.isActionSupported(PermissionType[type], PermissionAction[action])
      )
      .forEach((action) => {
        typeGroup.get(action).patchValue(event.target.checked)
      })

    if (this.typeHasAllActionsSelected(type)) {
      this.typesWithAllActions.add(type)
    } else {
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
      return Object.keys(PermissionAction)
        .filter((action) =>
          this.isActionSupported(
            PermissionType[typeKey],
            PermissionAction[action]
          )
        )
        .every((action) => {
          return this._inheritedPermissions.includes(
            this.permissionsService.getPermissionCode(
              PermissionAction[action],
              PermissionType[typeKey]
            )
          )
        })
    }
  }

  updateDisabledStates() {
    this.allowedTypes.forEach((type) => {
      const control = this.form.get(type)
      let actionControl: AbstractControl
      for (const action of Object.keys(PermissionAction)) {
        actionControl = control.get(action)
        if (
          !this.isActionSupported(
            PermissionType[type],
            PermissionAction[action]
          )
        ) {
          actionControl.patchValue(false, { emitEvent: false })
          actionControl.disable({ emitEvent: false })
          continue
        }

        this.isInherited(type, action) || this.disabled
          ? actionControl.disable({ emitEvent: false })
          : actionControl.enable({ emitEvent: false })
      }
    })
  }

  public isActionSupported(
    type: PermissionType,
    action: PermissionAction
  ): boolean {
    // Global statistics and system status only support view
    if (
      type === PermissionType.GlobalStatistics ||
      type === PermissionType.SystemMonitoring
    ) {
      return action === PermissionAction.View
    }

    return true
  }

  private getSelectedPermissions(formValue: object): string[] {
    const permissions = []
    Object.entries(formValue).forEach(([typeKey, typeValue]) => {
      Object.entries(typeValue)
        .filter(
          ([actionKey, actionValue]) =>
            actionValue &&
            this.isActionSupported(
              PermissionType[typeKey],
              PermissionAction[actionKey]
            )
        )
        .forEach(([actionKey]) => {
          permissions.push(
            this.permissionsService.getPermissionCode(
              PermissionAction[actionKey],
              PermissionType[typeKey]
            )
          )
        })
    })
    return permissions
  }

  private typeHasAllActionsSelected(typeKey: string): boolean {
    return Object.keys(PermissionAction)
      .filter((action) =>
        this.isActionSupported(
          PermissionType[typeKey],
          PermissionAction[action]
        )
      )
      .every((action) => !!this.form.get(typeKey)?.get(action)?.value)
  }

  public sortActions = (
    a: KeyValue<string, PermissionAction>,
    b: KeyValue<string, PermissionAction>
  ): number =>
    this.actionOrder.indexOf(a.value) - this.actionOrder.indexOf(b.value)
}
