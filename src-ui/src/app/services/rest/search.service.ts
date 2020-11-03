import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { SearchResult } from 'src/app/data/search-result';
import { environment } from 'src/environments/environment';


@Injectable({
  providedIn: 'root'
})
export class SearchService {
  
  constructor(private http: HttpClient) { }

  search(query: string, page?: number): Observable<SearchResult> {
    let httpParams = new HttpParams().set('query', query)
    if (page) {
      httpParams = httpParams.set('page', page.toString())
    }
    return this.http.get<SearchResult>(`${environment.apiBaseUrl}search/`, {params: httpParams})
  }

  autocomplete(term: string): Observable<string[]> {
    return this.http.get<string[]>(`${environment.apiBaseUrl}search/autocomplete/`, {params: new HttpParams().set('term', term)})
  }
} 
