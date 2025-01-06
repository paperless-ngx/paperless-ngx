import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'
import { Results } from '../data/results'
import { Backup } from '../data/backup'

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
}
