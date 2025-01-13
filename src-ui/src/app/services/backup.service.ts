import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'
import { Results } from '../data/results'
import { Backup } from '../data/backup'
import { PermissionsObject } from '../data/object-with-permissions'
import { BulkEditObjectOperation } from './rest/abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class BackupService {
  constructor(private http: HttpClient) {
  }

  public getRecordBackup(page: number = 1): Observable<Results<Backup>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Backup>>(`${environment.apiBaseUrl}backup_records/`, {
      params: httpParams,
    })
  }

  public restore(backup: number) {
    return this.http.post(`${environment.apiBaseUrl}backup_records/${backup}/restore/`, {})
  }

  public backup(): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}backup_records/`, {})
  }

  public deleteBackups(backups?: number[]): Observable<any> {
    const data = {
      action: 'empty',
    }
    if (backups?.length) {
      data['backups'] = backups
    }
    return this.http.post(`${environment.apiBaseUrl}backup_record/`, data)
  }

  bulk_edit_objects(
    objects: Array<number>,
    operation: BulkEditObjectOperation,
    permissions: { owner: number; set_permissions: PermissionsObject } = null,
    merge: boolean = null,
  ): Observable<string> {

    const params = {
      objects,
      object_type: 'backup_records',
      operation,
    }
    if (operation === BulkEditObjectOperation.SetPermissions) {
      params['owner'] = permissions?.owner
      params['permissions'] = permissions?.set_permissions
      params['merge'] = merge
    }
    return this.http.post<string>(`${environment.apiBaseUrl}bulk_edit_objects/`, params)
  }
}
