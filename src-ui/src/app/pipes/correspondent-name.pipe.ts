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
    const permissionsService = inject(PermissionsService)
    const objectService = inject(CorrespondentService)

    super(permissionsService, PermissionType.Correspondent, objectService)
  }
}
