import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'

@Injectable({
  providedIn: 'root',
})
export class TrashService {
  constructor(private http: HttpClient) {}

  public getTrash(): Observable<Document[]> {
    return this.http.get<Document[]>(`${environment.apiBaseUrl}trash/`)
  }

  public emptyTrash(documents: number[] = []): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}trash/`, {
      action: 'empty',
      documents,
    })
  }

  public restoreDocuments(documents: number[]): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}trash/`, {
      action: 'restore',
      documents,
    })
  }
}
