import { Pipe, PipeTransform } from '@angular/core'
import { catchError, map, Observable, of } from 'rxjs'
import { User } from '../data/user'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'
import { UserService } from '../services/rest/user.service'

@Pipe({
  name: 'username',
})
export class UsernamePipe implements PipeTransform {
  users: User[]

  constructor(
    private permissionsService: PermissionsService,
    private userService: UserService
  ) {}

  transform(userID: number): Observable<string> {
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.User
      )
    ) {
      return this.userService.listAll().pipe(
        map((users) => {
          this.users = users.results
          return this.getName(this.users.find((u) => u.id === userID))
        }),
        catchError(() => of(''))
      )
    } else {
      return of($localize`Shared`)
    }
  }

  getName(user: User): string {
    if (!user) return ''
    const name = [user.first_name, user.last_name].join(' ')
    if (name.length > 1) return name.trim()
    return user.username
  }
}
