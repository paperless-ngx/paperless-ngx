import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { FormControl, FormGroup, NG_VALUE_ACCESSOR } from '@angular/forms'
import { PaperlessUser } from 'src/app/data/paperless-user'
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
  users: PaperlessUser[]

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
}
