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
    // dont pass string
    if (typeof config.app_logo === 'string') delete config.app_logo
    return this.http
      .patch<PaperlessConfig>(`${this.baseUrl}${config.id}/`, config)
      .pipe(first())
  }

  uploadFile(
    file: File,
    configID: number,
    configKey: string
  ): Observable<PaperlessConfig> {
    let formData = new FormData()
    formData.append(configKey, file, file.name)
    return this.http
      .patch<PaperlessConfig>(`${this.baseUrl}${configID}/`, formData)
      .pipe(first())
  }
}
