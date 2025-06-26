import { inject, Pipe, PipeTransform } from '@angular/core'
import {
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'
import { StoragePathService } from '../services/rest/storage-path.service'
import { ObjectNamePipe } from './object-name.pipe'

@Pipe({
  name: 'storagePathName',
})
export class StoragePathNamePipe
  extends ObjectNamePipe
  implements PipeTransform
{
  constructor() {
    const permissionsService = inject(PermissionsService)
    const objectService = inject(StoragePathService)

    super(permissionsService, PermissionType.StoragePath, objectService)
  }
}
