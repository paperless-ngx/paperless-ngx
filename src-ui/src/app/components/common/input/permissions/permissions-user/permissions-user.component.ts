import { Component, forwardRef, inject } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgSelectComponent } from '@ng-select/ng-select'
import { first } from 'rxjs/operators'
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
  users: User[]

  constructor() {
    const userService = inject(UserService)

    super()
    userService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.users = result.results))
  }
}
