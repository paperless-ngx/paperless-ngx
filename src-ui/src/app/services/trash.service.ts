import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import { Document } from '../data/document'
import { Results } from '../data/results'

@Injectable({
  providedIn: 'root',
})
export class TrashService {
  constructor(private http: HttpClient) {}

  public getTrash(page: number = 1): Observable<Results<Document>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Document>>(`${environment.apiBaseUrl}trash/`, {
      params: httpParams,
    })
  }

  public emptyTrash(documents?: number[]): Observable<any> {
    const data = {
      action: 'empty',
    }
    if (documents?.length) {
      data['documents'] = documents
    }
    return this.http.post(`${environment.apiBaseUrl}trash/`, data)
  }

  public restoreDocuments(documents: number[]): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}trash/`, {
      action: 'restore',
      documents,
    })
  }
}
