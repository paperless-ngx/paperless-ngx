import { Pipe, PipeTransform } from '@angular/core'
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
  constructor(
    permissionsService: PermissionsService,
    objectService: CorrespondentService
  ) {
    super(permissionsService, PermissionType.Correspondent, objectService)
  }
}
