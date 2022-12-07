import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { first } from 'rxjs/operators'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { UserService } from 'src/app/services/rest/user.service'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => ShareUserComponent),
      multi: true,
    },
  ],
  selector: 'app-share-user',
  templateUrl: './share-user.component.html',
  styleUrls: ['./share-user.component.scss'],
})
export class ShareUserComponent
  extends AbstractInputComponent<PaperlessUser>
  implements OnInit
{
  users: PaperlessUser[]

  @Input()
  type: string

  constructor(userService: UserService) {
    super()
    userService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.users = result.results))
  }

  ngOnInit(): void {
    if (this.type == 'view') {
      this.title = $localize`Users can view`
    } else if (this.type == 'change') {
      this.title = $localize`Users can edit`
      this.hint = $localize`Edit permissions also grant viewing permissions`
    }

    super.ngOnInit()
  }
}
