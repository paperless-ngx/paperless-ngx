import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class LogService {
  private http = inject(HttpClient)

  list(): Observable<string[]> {
    return this.http.get<string[]>(`${environment.apiBaseUrl}logs/`)
  }

  get(id: string, limit?: number): Observable<string[]> {
    let params = new HttpParams()
    if (limit !== undefined) {
      params = params.set('limit', limit.toString())
    }
    return this.http.get<string[]>(`${environment.apiBaseUrl}logs/${id}/`, {
      params,
    })
  }
}
