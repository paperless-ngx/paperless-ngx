import { Injectable, inject } from '@angular/core'
import { Observable, switchMap } from 'rxjs'
import { Group } from 'src/app/data/group'
import { PermissionsService } from '../permissions.service'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class GroupService extends AbstractNameFilterService<Group> {
  private permissionService = inject(PermissionsService)

  constructor() {
    super()
    this.resourceName = 'groups'
  }

  update(o: Group): Observable<Group> {
    return this.getCached(o.id).pipe(
      switchMap((initialGroup) => {
        initialGroup.permissions?.forEach((perm) => {
          const { typeKey, actionKey } =
            this.permissionService.getPermissionKeys(perm)
          if (!typeKey || !actionKey) {
            // dont lose permissions the UI doesn't use
            o.permissions.push(perm)
          }
        })
        return super.update(o)
      })
    )
  }
}
