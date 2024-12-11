import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { FormControl, FormGroup, NG_VALUE_ACCESSOR } from '@angular/forms'
import { User } from 'src/app/data/user'
import { AbstractInputComponent } from '../../abstract-input'

export interface PermissionsFormObject {
  owner?: number
  set_permissions?: {
    view?: {
      users?: number[]
      groups?: number[]
    }
    change?: {
      users?: number[]
      groups?: number[]
    }
  }
}

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsFormComponent),
      multi: true,
    },
  ],
  selector: 'pngx-permissions-form',
  templateUrl: './permissions-form.component.html',
  styleUrls: ['./permissions-form.component.scss'],
})
export class PermissionsFormComponent
  extends AbstractInputComponent<PermissionsFormObject>
  implements OnInit
{
  @Input()
  users: User[]

  @Input()
  accordion: boolean = false

  form = new FormGroup({
    owner: new FormControl(null),
    set_permissions: new FormGroup({
      view: new FormGroup({
        users: new FormControl([]),
        groups: new FormControl([]),
      }),
      change: new FormGroup({
        users: new FormControl([]),
        groups: new FormControl([]),
      }),
    }),
  })

  constructor() {
    super()
  }

  ngOnInit(): void {
    this.form.valueChanges.subscribe((value) => {
      this.onChange(value)
    })
  }

  writeValue(newValue: any): void {
    this.form.patchValue(newValue, { emitEvent: false })
  }

  public setDisabledState(isDisabled: boolean): void {
    if (isDisabled) {
      this.form.disable()
    } else {
      this.form.enable()
    }
  }
}
