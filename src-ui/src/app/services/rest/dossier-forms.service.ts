import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { Observable } from 'rxjs'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { DossierForm } from 'src/app/data/dossier-form'


@Injectable({
  providedIn: 'root',
})
export class DossierFormService extends AbstractNameFilterService<DossierForm> {
  constructor(http: HttpClient) {
    super(http, 'dossier_forms')
  }
  // getDossierPath(id: number): Observable<DossierForm> {
  //   return this.http.get<DossierForm>(this.getResourceUrl(id, 'dossier_path'))
  // }
}