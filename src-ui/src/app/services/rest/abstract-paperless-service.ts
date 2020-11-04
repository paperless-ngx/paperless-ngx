import { HttpClient, HttpParams } from '@angular/common/http'
import { Observable } from 'rxjs'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { Results } from 'src/app/data/results'
import { environment } from 'src/environments/environment'

export abstract class AbstractPaperlessService<T extends ObjectWithId> {

  protected baseUrl: string = environment.apiBaseUrl

  constructor(protected http: HttpClient, private resourceName: string) { }

  protected getResourceUrl(id?: number, action?: string): string {
    let url = `${this.baseUrl}${this.resourceName}/`
    if (id) {
      url += `${id}/`
    }
    if (action) {
      url += `${action}/`
    }
    return url
  }

  list(page?: number, pageSize?: number, ordering?: string, extraParams?): Observable<Results<T>> {
    let httpParams = new HttpParams()
    if (page) {
      httpParams = httpParams.set('page', page.toString())
    }
    if (pageSize) {
      httpParams = httpParams.set('page_size', pageSize.toString())
    }
    if (ordering) {
      httpParams = httpParams.set('ordering', ordering)
    }
    for (let extraParamKey in extraParams) {
      if (extraParams[extraParamKey] != null) {
        httpParams = httpParams.set(extraParamKey, extraParams[extraParamKey])
      }
    }
    return this.http.get<Results<T>>(this.getResourceUrl(), {params: httpParams})
  }

  listAll(ordering?: string, extraParams?): Observable<Results<T>> {
    return this.list(1, 100000, ordering, extraParams)
  }

  get(id: number): Observable<T> {
    return this.http.get<T>(this.getResourceUrl(id))
  }

  create(o: T): Observable<T> {
    return this.http.post<T>(this.getResourceUrl(), o)
  }

  delete(o: T): Observable<any> {
    return this.http.delete(this.getResourceUrl(o.id))
  }

  update(o: T): Observable<T> {
    return this.http.put<T>(this.getResourceUrl(o.id), o)
  }
}