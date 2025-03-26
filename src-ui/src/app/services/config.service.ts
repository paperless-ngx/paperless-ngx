import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, first, map } from 'rxjs'
import { environment } from 'src/environments/environment'
import { EdocConfig } from '../data/edoc-config'

@Injectable({
  providedIn: 'root',
})
export class ConfigService {
  protected baseUrl: string = environment.apiBaseUrl + 'config/'

  constructor(protected http: HttpClient) {}

  getConfig(): Observable<EdocConfig> {
    return this.http.get<[EdocConfig]>(this.baseUrl).pipe(
      first(),
      map((configs) => configs[0])
    )
  }

  saveConfig(config: EdocConfig): Observable<EdocConfig> {
    // dont pass string
    if (typeof config.app_logo === 'string') delete config.app_logo
    return this.http
      .patch<EdocConfig>(`${this.baseUrl}${config.id}/`, config)
      .pipe(first())
  }

  uploadFile(
    file: File,
    configID: number,
    configKey: string
  ): Observable<EdocConfig> {
    let formData = new FormData()
    formData.append(configKey, file, file.name)
    return this.http
      .patch<EdocConfig>(`${this.baseUrl}${configID}/`, formData)
      .pipe(first())
  }
}
