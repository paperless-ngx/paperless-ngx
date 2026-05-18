import { HttpClient, HttpParams } from '@angular/common/http'
import { inject, Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { map, shareReplay, tap } from 'rxjs/operators'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { Results } from 'src/app/data/results'
import { environment } from 'src/environments/environment'
@Injectable({
  providedIn: 'root',
})
export abstract class AbstractPaperlessService<T extends ObjectWithId> {
  protected baseUrl: string = environment.apiBaseUrl
  protected http: HttpClient
  protected resourceName: string

  protected _loading: boolean = false
  public get loading(): boolean {
    return this._loading
  }

  constructor() {
    this.http = inject(HttpClient)
  }

  protected getResourceUrl(id: number = null, action: string = null): string {
    let url = `${this.baseUrl}${this.resourceName}/`
    if (id !== null) {
      url += `${id}/`
    }
    if (action) {
      url += `${action}/`
    }
    return url
  }

  private getOrderingQueryParam(sortField: string, sortReverse: boolean) {
    if (sortField) {
      return (sortReverse ? '-' : '') + sortField
    } else {
      return null
    }
  }

  list(
    page?: number,
    pageSize?: number,
    sortField?: string,
    sortReverse?: boolean,
    extraParams?
  ): Observable<Results<T>> {
    this._loading = true
    let httpParams = new HttpParams()
    if (page) {
      httpParams = httpParams.set('page', page.toString())
    }
    if (pageSize) {
      httpParams = httpParams.set('page_size', pageSize.toString())
    }
    let ordering = this.getOrderingQueryParam(sortField, sortReverse)
    if (ordering) {
      httpParams = httpParams.set('ordering', ordering)
    }
    for (let extraParamKey in extraParams) {
      if (extraParams[extraParamKey] != null) {
        httpParams = httpParams.set(extraParamKey, extraParams[extraParamKey])
      }
    }
    return this.http
      .get<Results<T>>(this.getResourceUrl(), {
        params: httpParams,
      })
      .pipe(
        tap(() => {
          this._loading = false
        })
      )
  }

  private _listAll: Observable<Results<T>>

  listAll(
    sortField?: string,
    sortReverse?: boolean,
    extraParams?
  ): Observable<Results<T>> {
    if (!this._listAll) {
      this._listAll = this.list(
        1,
        100000,
        sortField,
        sortReverse,
        extraParams
      ).pipe(shareReplay({ bufferSize: 1, refCount: true }))
    }
    return this._listAll
  }

  getCached(id: number): Observable<T> {
    return this.listAll().pipe(
      map((list) => list.results.find((o) => o.id == id))
    )
  }

  getCachedMany(ids: number[]): Observable<T[]> {
    return this.listAll().pipe(
      map((list) => ids.map((id) => list.results.find((o) => o.id == id)))
    )
  }

  getFew(ids: number[], extraParams?): Observable<Results<T>> {
    this._loading = true
    let httpParams = new HttpParams()
    httpParams = httpParams.set('id__in', ids.join(','))
    httpParams = httpParams.set('ordering', '-id')
    httpParams = httpParams.set('page_size', 1000)
    for (let extraParamKey in extraParams) {
      if (extraParams[extraParamKey] != null) {
        httpParams = httpParams.set(extraParamKey, extraParams[extraParamKey])
      }
    }
    return this.http
      .get<Results<T>>(this.getResourceUrl(), {
        params: httpParams,
      })
      .pipe(
        tap(() => {
          this._loading = false
        })
      )
  }

  clearCache() {
    this._listAll = null
  }

  get(id: number): Observable<T> {
    this._loading = true
    return this.http.get<T>(this.getResourceUrl(id)).pipe(
      tap(() => {
        this._loading = false
      })
    )
  }

  create(o: T): Observable<T> {
    this.clearCache()
    return this.http.post<T>(this.getResourceUrl(), o)
  }

  delete(o: T): Observable<any> {
    this.clearCache()
    return this.http.delete(this.getResourceUrl(o.id))
  }

  update(o: T): Observable<T> {
    this.clearCache()
    return this.http.put<T>(this.getResourceUrl(o.id), o)
  }

  patch(o: T): Observable<T> {
    this.clearCache()
    return this.http.patch<T>(this.getResourceUrl(o.id), o)
  }
}
