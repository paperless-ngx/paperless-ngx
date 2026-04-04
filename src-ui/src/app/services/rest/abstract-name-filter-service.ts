import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { PermissionsObject } from 'src/app/data/object-with-permissions'
import { AbstractPaperlessService } from './abstract-paperless-service'

export enum BulkEditObjectOperation {
  SetPermissions = 'set_permissions',
  Delete = 'delete',
}
@Injectable({
  providedIn: 'root',
})
export abstract class AbstractNameFilterService<
  T extends ObjectWithId,
> extends AbstractPaperlessService<T> {
  listFiltered(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    nameFilter?: string,
    fullPerms?: boolean,
    extraParams?: { [key: string]: any }
  ) {
    let params = extraParams ?? {}
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
    merge: boolean = null,
    all: boolean = false,
    filters: { [key: string]: any } = null
  ): Observable<string> {
    const params: any = {
      object_type: this.resourceName,
      operation,
    }
    if (all) {
      params['all'] = true
      if (filters) {
        params['filters'] = filters
      }
    } else {
      params['objects'] = objects
    }
    if (operation === BulkEditObjectOperation.SetPermissions) {
      params['owner'] = permissions?.owner
      params['permissions'] = permissions?.set_permissions
      params['merge'] = merge
    }
    return this.http.post<string>(`${this.baseUrl}bulk_edit_objects/`, params)
  }
}
