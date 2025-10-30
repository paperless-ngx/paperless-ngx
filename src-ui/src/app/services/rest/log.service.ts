import { HttpClient } from '@angular/common/http'
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

  get(id: string, options?: { tail?: number }): Observable<string[]> {
    const params = options?.tail ? { tail: options.tail.toString() } : {}
    return this.http.get<string[]>(`${environment.apiBaseUrl}logs/${id}/`, { params })
  }
}
