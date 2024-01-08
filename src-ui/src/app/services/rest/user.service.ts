import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, switchMap } from 'rxjs'
import { User } from 'src/app/data/user'
import { PermissionsService } from '../permissions.service'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class UserService extends AbstractNameFilterService<User> {
  constructor(
    http: HttpClient,
    private permissionService: PermissionsService
  ) {
    super(http, 'users')
  }

  update(o: User): Observable<User> {
    return this.getCached(o.id).pipe(
      switchMap((initialUser) => {
        initialUser.user_permissions?.forEach((perm) => {
          const { typeKey, actionKey } =
            this.permissionService.getPermissionKeys(perm)
          if (!typeKey || !actionKey) {
            // dont lose permissions the UI doesn't use
            o.user_permissions.push(perm)
          }
        })
        return super.update(o)
      })
    )
  }
}
