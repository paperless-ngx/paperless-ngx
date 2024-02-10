import { ObjectWithId } from 'src/app/data/object-with-id'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { PermissionsObject } from 'src/app/data/object-with-permissions'
import { Observable } from 'rxjs'

export enum BulkEditObjectOperation {
  SetPermissions = 'set_permissions',
  Delete = 'delete',
}

export abstract class AbstractNameFilterService<
  T extends ObjectWithId,
> extends AbstractPaperlessService<T> {
  listFiltered(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    nameFilter?: string,
    fullPerms?: boolean
  ) {
    let params = {}
    if (nameFilter) {
      params['name__icontains'] = nameFilter
    }
    if (fullPerms) {
      params['full_perms'] = true
    }
    return this.list(page, pageSize, sortField, sortReverse, params)
  }

  bulk_edit_objects(
    objects: Array<number>,
    operation: BulkEditObjectOperation,
    permissions: { owner: number; set_permissions: PermissionsObject } = null,
    merge: boolean = null
  ): Observable<string> {
    const params = {
      objects,
      object_type: this.resourceName,
      operation,
    }
    if (operation === BulkEditObjectOperation.SetPermissions) {
      params['owner'] = permissions?.owner
      params['permissions'] = permissions?.set_permissions
      params['merge'] = merge
    }
    return this.http.post<string>(`${this.baseUrl}bulk_edit_objects/`, params)
  }
}
