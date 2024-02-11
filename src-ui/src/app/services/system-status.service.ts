import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { PaperlessSystemStatus } from '../data/system-status'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class SystemStatusService {
  private endpoint = 'status'

  constructor(private http: HttpClient) {}

  get(): Observable<PaperlessSystemStatus> {
    return this.http.get<PaperlessSystemStatus>(
      `${environment.apiBaseUrl}${this.endpoint}/`
    )
  }
}
