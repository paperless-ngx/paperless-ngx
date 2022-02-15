import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from 'src/environments/environment';
import { DocumentService } from './document.service';


@Injectable({
  providedIn: 'root'
})
export class SearchService {

  constructor(private http: HttpClient) { }

  autocomplete(term: string): Observable<string[]> {
    return this.http.get<string[]>(`${environment.apiBaseUrl}search/autocomplete/`, {params: new HttpParams().set('term', term)})
  }
}
