import { Injectable, inject } from '@angular/core'
import { Observable, switchMap } from 'rxjs'
import { User } from 'src/app/data/user'
import { PermissionsService } from '../permissions.service'
import { AbstractNameFilterService } from './abstract-name-filter-service'

const endpoint = 'users'
@Injectable({
  providedIn: 'root',
})
export class UserService extends AbstractNameFilterService<User> {
  private permissionService = inject(PermissionsService)

  constructor() {
    super()
    this.resourceName = endpoint
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

  deactivateTotp(u: User): Observable<boolean> {
    return this.http.post<boolean>(
      `${this.getResourceUrl(u.id, 'deactivate_totp')}`,
      null
    )
  }
}
