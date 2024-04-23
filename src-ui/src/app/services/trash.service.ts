import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { ObjectWithId } from '../data/object-with-id'

@Injectable({
  providedIn: 'root',
})
export class TrashService {
  constructor(private http: HttpClient) {}

  public getTrash(): Observable<ObjectWithId[]> {
    return this.http.get<ObjectWithId[]>(`${environment.apiBaseUrl}trash/`)
  }

  public emptyTrash(documents: number[] = []) {
    return this.http.post(`${environment.apiBaseUrl}trash/`, {
      action: 'empty',
      documents,
    })
  }

  public restoreObjects(documents: number[]): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}trash/`, {
      action: 'restore',
      documents,
    })
  }
}
