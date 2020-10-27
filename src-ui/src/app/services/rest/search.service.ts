import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { environment } from 'src/environments/environment';

export class SearchResultHighlightedText {
  text?: string
  term?: number

  toString(): string {
    return this.text
  }
}

export class SearchResult {
  id?: number
  title?: string
  content?: string

  score?: number
  highlights?: SearchResultHighlightedText[][]

  document?: PaperlessDocument
}

@Injectable({
  providedIn: 'root'
})
export class SearchService {
  
  constructor(private http: HttpClient) { }

  search(query: string): Observable<SearchResult[]> {
    return this.http.get<SearchResult[]>(`${environment.apiBaseUrl}search/`, {params: new HttpParams().set('query', query)})
  }
} 
