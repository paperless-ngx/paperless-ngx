import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { SystemStorageStatus } from '../data/system-storage-status'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class SystemStatusService {
  private endpoint = 'status_storage'

  constructor(private http: HttpClient) {
  }

  get(): Observable<SystemStorageStatus> {
    return this.http.get<SystemStorageStatus>(
      `${environment.apiBaseUrl}${this.endpoint}/`,
    )
  }
}
