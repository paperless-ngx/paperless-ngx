import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, switchMap } from 'rxjs'
import { PaperlessUser } from 'src/app/data/paperless-user'
import { PermissionsService } from '../permissions.service'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class UserService extends AbstractNameFilterService<PaperlessUser> {
  constructor(
    http: HttpClient,
    private permissionService: PermissionsService
  ) {
    super(http, 'users')
  }

  update(o: PaperlessUser): Observable<PaperlessUser> {
    return this.getCached(o.id).pipe(
      switchMap((initialUser) => {
        initialUser.user_permissions?.forEach((perm) => {
          const { typeKey, actionKey } =
            this.permissionService.getPermissionKeys(perm)
          if (!typeKey || !actionKey) {
            // dont lose permissions the UI doesnt use
            o.user_permissions.push(perm)
          }
        })
        return super.update(o)
      })
    )
  }
}
