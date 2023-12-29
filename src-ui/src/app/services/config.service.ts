import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, first, map } from 'rxjs'
import { environment } from 'src/environments/environment'
import { PaperlessConfig } from '../data/paperless-config'

@Injectable({
  providedIn: 'root',
})
export class ConfigService {
  protected baseUrl: string = environment.apiBaseUrl + 'config/'

  constructor(protected http: HttpClient) {}

  getConfig(): Observable<PaperlessConfig> {
    return this.http.get<[PaperlessConfig]>(this.baseUrl).pipe(
      first(),
      map((configs) => configs[0])
    )
  }

  saveConfig(config: PaperlessConfig): Observable<PaperlessConfig> {
    return this.http
      .patch<PaperlessConfig>(`${this.baseUrl}${config.id}/`, config)
      .pipe(first())
  }
}
