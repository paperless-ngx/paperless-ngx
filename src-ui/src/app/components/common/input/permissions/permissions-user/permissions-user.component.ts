import { Component, forwardRef, inject } from '@angular/core'
import { toSignal } from '@angular/core/rxjs-interop'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgSelectComponent } from '@ng-select/ng-select'
import { map } from 'rxjs/operators'
import { User } from 'src/app/data/user'
import { UserService } from 'src/app/services/rest/user.service'
import { AbstractInputComponent } from '../../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsUserComponent),
      multi: true,
    },
  ],
  selector: 'pngx-permissions-user',
  templateUrl: './permissions-user.component.html',
  styleUrls: ['./permissions-user.component.scss'],
  imports: [NgSelectComponent, FormsModule, ReactiveFormsModule],
})
export class PermissionsUserComponent extends AbstractInputComponent<User[]> {
  private readonly userService = inject(UserService)
  readonly users = toSignal(
    this.userService.listAll().pipe(map((result) => result.results)),
    { initialValue: undefined as User[] }
  )
}
