import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { Observable } from 'rxjs'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { Dossier } from 'src/app/data/dossier'


@Injectable({
  providedIn: 'root',
})
export class DossierService extends AbstractNameFilterService<Dossier> {
  constructor(http: HttpClient) {
    super(http, 'dossiers')
  }
  getDossierPath(id: number): Observable<Dossier> {
    return this.http.get<Dossier>(this.getResourceUrl(id, 'dossier_path'))
  }
}