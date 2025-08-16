import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { SystemStatus } from '../data/system-status'

@Injectable({
  providedIn: 'root',
})
export class SystemStatusService {
  private http = inject(HttpClient)

  private endpoint = 'status'

  get(): Observable<SystemStatus> {
    return this.http.get<SystemStatus>(
      `${environment.apiBaseUrl}${this.endpoint}/`
    )
  }
}
