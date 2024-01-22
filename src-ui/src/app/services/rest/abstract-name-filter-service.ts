import { ObjectWithId } from 'src/app/data/object-with-id'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { PermissionsObject } from 'src/app/data/object-with-permissions'
import { Observable } from 'rxjs'

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

  bulk_update_permissions(
    objects: Array<number>,
    permissions: { owner: number; set_permissions: PermissionsObject },
    merge: boolean
  ): Observable<string> {
    return this.http.post<string>(`${this.baseUrl}bulk_edit_object_perms/`, {
      objects,
      object_type: this.resourceName,
      owner: permissions.owner,
      permissions: permissions.set_permissions,
      merge,
    })
  }
}
