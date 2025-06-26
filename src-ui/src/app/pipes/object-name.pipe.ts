import { inject, Pipe, PipeTransform } from '@angular/core'
import { catchError, map, Observable, of } from 'rxjs'
import { MatchingModel } from '../data/matching-model'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'
import { AbstractNameFilterService } from '../services/rest/abstract-name-filter-service'

@Pipe({
  name: 'objectName',
})
export abstract class ObjectNamePipe implements PipeTransform {
  protected permissionsService = inject(PermissionsService)
  protected permissionType: PermissionType
  protected objectService = inject<AbstractNameFilterService<MatchingModel>>(
    AbstractNameFilterService
  )

  /*
    ObjectNamePipe is an abstract class to prevent instantiation,
    object-specific pipes extend this class and provide the
    correct permission type, and object service.
  */
  protected objects: MatchingModel[]

  transform(obejctId: number): Observable<string> {
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        this.permissionType
      )
    ) {
      return this.objectService.listAll().pipe(
        map((objects) => {
          this.objects = objects.results
          return (
            this.objects.find((o) => o.id === obejctId)?.name ||
            $localize`Private`
          )
        }),
        catchError(() => of(''))
      )
    } else {
      return of($localize`Private`)
    }
  }
}
