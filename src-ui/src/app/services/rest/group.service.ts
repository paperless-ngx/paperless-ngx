import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, switchMap } from 'rxjs'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { PermissionsService } from '../permissions.service'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class GroupService extends AbstractNameFilterService<PaperlessGroup> {
  constructor(
    http: HttpClient,
    private permissionService: PermissionsService
  ) {
    super(http, 'groups')
  }

  update(o: PaperlessGroup): Observable<PaperlessGroup> {
    return this.getCached(o.id).pipe(
      switchMap((initialGroup) => {
        initialGroup.permissions?.forEach((perm) => {
          const { typeKey, actionKey } =
            this.permissionService.getPermissionKeys(perm)
          if (!typeKey || !actionKey) {
            // dont lose permissions the UI doesnt use
            o.permissions.push(perm)
          }
        })
        return super.update(o)
      })
    )
  }
}
