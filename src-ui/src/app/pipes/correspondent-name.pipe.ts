import { inject, Pipe, PipeTransform } from '@angular/core'
import {
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'
import { CorrespondentService } from '../services/rest/correspondent.service'
import { ObjectNamePipe } from './object-name.pipe'

@Pipe({
  name: 'correspondentName',
})
export class CorrespondentNamePipe
  extends ObjectNamePipe
  implements PipeTransform
{
  constructor() {
    super()
    this.permissionsService = inject(PermissionsService)
    this.permissionType = PermissionType.Correspondent
    this.objectService = inject(CorrespondentService)
  }
}
