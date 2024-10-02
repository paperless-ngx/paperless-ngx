import { ObjectWithId } from 'src/app/data/object-with-id'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { PermissionsObject } from 'src/app/data/object-with-permissions'
import { Observable } from 'rxjs'

export enum BulkEditObjectOperation {
  SetPermissions = 'set_permissions',
  Delete = 'delete',
  Update = 'update',
  Share = "Share",
}

export abstract class AbstractNameFilterService<T extends ObjectWithId,> extends AbstractPaperlessService<T> {
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
    params['type__iexact'] = 'Warehouse'

    return this.list(page, pageSize, sortField, sortReverse, params)
  }

  listFolderFiltered(page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    id?: number,
    nameFilter?: string,
    fullPerms?: boolean) {
    let params = {}
    if (id) {
      params['parent_folder__id'] = id
    }
    else{
      params['parent_folder__isnull'] = true
    }
    if (nameFilter) {
      params['name__icontains'] = nameFilter
    }
    if (fullPerms) {
      params['full_perms'] = true
    }
 
    return this.list(page, pageSize, sortField, sortReverse, params)
  }

  listDossierFiltered(page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    id?: number,
    nameFilter?: string,
    fullPerms?: boolean,
    type?: string) {
    let params = {}
    if (id) {
      params['parent_dossier__id'] = id
    }
    else{
      params['parent_dossier__isnull'] = true
    }
    if (nameFilter) {
      params['name__icontains'] = nameFilter
    }
    if (fullPerms) {
      params['full_perms'] = true
    }
    if (type.length){
      params['type'] = type
    }
 
    return this.list(page, pageSize, sortField, sortReverse, params)
  }
  
  listDossierFormFiltered(page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    id?: number,
    nameFilter?: string,
    fullPerms?: boolean,
    type?: string) {
    let params = {}
    if (id) {
      params['parent_dossier__id'] = id
    }
    if (nameFilter) {
      params['name__icontains'] = nameFilter
    }
    if (fullPerms) {
      params['full_perms'] = true
    }
    if (type.length){
      params['type'] = type
    }
 
    return this.list(page, pageSize, sortField, sortReverse, params)
  }

  listGia(page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    nameFilter?: string,
    fullPerms?: boolean) {
    let params = {}
    if (nameFilter) {
      params['name__icontains'] = nameFilter
    }
    if (fullPerms) {
      params['full_perms'] = true
    }
    params['type__iexact'] = 'Shelf'

    return this.list(page, pageSize, sortField, sortReverse, params)
  }

  listBox(page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    nameFilter?: string,
    fullPerms?: boolean) {
    let params = {}
    if (nameFilter) {
      params['name__icontains'] = nameFilter
    }
    if (fullPerms) {
      params['full_perms'] = true
    }
    params['type__iexact'] = 'Boxcase'

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

  bulk_edit_folders(
    objects: Array<number>,
    parent_folder: number,
    operation: BulkEditObjectOperation,
    permissions: { owner: number; set_permissions: PermissionsObject } = null,
    merge: boolean = null
  ): Observable<string> {
    const params = {
      objects,
      object_type: this.resourceName,
      operation,
      parent_folder,
    }
    if (operation === BulkEditObjectOperation.SetPermissions) {
      params['owner'] = permissions?.owner
      params['permissions'] = permissions?.set_permissions
      params['merge'] = merge
    }
    return this.http.post<string>(`${this.baseUrl}bulk_edit_objects/`, params)
  }

  // getDocuments(id: any): Observable<any> {

  //   return this.http.get<any>(`${this.baseUrl}warehouses/?parent_warehouse=${id}`, {});
  // }




}
