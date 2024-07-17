import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from 'src/environments/environment'
import { ContentType } from 'src/app/data/content-type';

@Injectable({
  providedIn: 'root',
})
export class ContentTypeService  {
  private endpoint = 'content_types'

  constructor(private http: HttpClient) {}

  listAll(): Observable<ContentType[]> {
    return this.http.get<ContentType[]>(
      `${environment.apiBaseUrl}${this.endpoint}/`
    )
  }
}
