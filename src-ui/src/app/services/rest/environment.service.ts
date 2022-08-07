import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { PaperlessEnvironment } from 'src/app/data/paperless-environment';
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root'
})
export class EnvironmentService {

  protected baseUrl: string = environment.apiBaseUrl

  constructor(protected http: HttpClient) { }

  get(environment: string): Observable<PaperlessEnvironment> {
    let httpParams = new HttpParams();
    httpParams = httpParams.set('name', environment);

    return this.http.get<PaperlessEnvironment>(`${this.baseUrl}environment/`, {params: httpParams})
  }
}