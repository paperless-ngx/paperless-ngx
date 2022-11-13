import { Component, forwardRef, Input, OnInit } from '@angular/core'
import {
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
import { AbstractInputComponent } from '../input/abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsSelectComponent),
      multi: true,
    },
  ],
  selector: 'app-permissions-select',
  templateUrl: './permissions-select.component.html',
  styleUrls: ['./permissions-select.component.scss'],
})
export class PermissionsSelectComponent
  implements OnInit, ControlValueAccessor
{
  PermissionType = PermissionType
  PermissionAction = PermissionAction

  @Input()
  title: string = 'Permissions'

  permissions: string[]

  form = new FormGroup({})

  constructor(private readonly permissionsService: PermissionsService) {
    for (const type in PermissionType) {
      const control = new FormGroup({})
      control.addControl('all', new FormControl(null))
      for (const action in PermissionAction) {
        control.addControl(action, new FormControl(null))
      }
      this.form.addControl(type, control)
    }
  }

  writeValue(permissions: string[]): void {
    this.permissions = permissions
    this.permissions.forEach((permissionStr) => {
      const { actionKey, typeKey } =
        this.permissionsService.getPermissionKeys(permissionStr)

      if (actionKey && typeKey) {
        if (this.form.get(typeKey)?.get(actionKey)) {
          this.form.get(typeKey).get(actionKey).setValue(true)
        }
      }
    })
  }
  registerOnChange(fn: any): void {
    throw new Error('Method not implemented.')
  }
  registerOnTouched(fn: any): void {
    throw new Error('Method not implemented.')
  }
  setDisabledState?(isDisabled: boolean): void {
    throw new Error('Method not implemented.')
  }

  ngOnInit(): void {}

  isAll(key: string): boolean {
    return this.form.get(key).get('all').value == true
  }
}
