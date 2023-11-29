import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { first } from 'rxjs/operators'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
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
})
export class PermissionsUserComponent extends AbstractInputComponent<
  PaperlessUser[]
> {
  users: PaperlessUser[]

  constructor(userService: UserService, settings: SettingsService) {
    super()
    userService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.users = result.results))
  }
}
