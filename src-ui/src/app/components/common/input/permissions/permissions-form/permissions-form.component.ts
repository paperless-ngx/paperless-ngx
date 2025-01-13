import { NgTemplateOutlet } from '@angular/common'
import { Component, forwardRef, Input, OnInit } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbAccordionModule } from '@ng-bootstrap/ng-bootstrap'
import { User } from 'src/app/data/user'
import { AbstractInputComponent } from '../../abstract-input'
import { SelectComponent } from '../../select/select.component'
import { PermissionsGroupComponent } from '../permissions-group/permissions-group.component'
import { PermissionsUserComponent } from '../permissions-user/permissions-user.component'

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
  imports: [
    SelectComponent,
    PermissionsUserComponent,
    PermissionsGroupComponent,
    FormsModule,
    ReactiveFormsModule,
    NgTemplateOutlet,
    NgbAccordionModule,
  ],
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
