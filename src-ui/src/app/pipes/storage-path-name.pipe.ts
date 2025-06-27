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
    super()
    this.permissionsService = inject(PermissionsService)
    this.permissionType = PermissionType.StoragePath
    this.objectService = inject(StoragePathService)
  }
}
