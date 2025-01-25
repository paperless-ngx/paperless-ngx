import { Pipe, PipeTransform } from '@angular/core'
import {
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'
import { DocumentTypeService } from '../services/rest/document-type.service'
import { ObjectNamePipe } from './object-name.pipe'

@Pipe({
  name: 'documentTypeName',
})
export class DocumentTypeNamePipe
  extends ObjectNamePipe
  implements PipeTransform
{
  constructor(
    permissionsService: PermissionsService,
    objectService: DocumentTypeService
  ) {
    super(permissionsService, PermissionType.DocumentType, objectService)
  }
}
