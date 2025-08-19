import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'

export interface AppRemoteVersion {
  version: string
  update_available: boolean
}

@Injectable({
  providedIn: 'root',
})
export class RemoteVersionService {
  private http = inject(HttpClient)

  public checkForUpdates(): Observable<AppRemoteVersion> {
    return this.http.get<AppRemoteVersion>(
      `${environment.apiBaseUrl}remote_version/`
    )
  }
}
