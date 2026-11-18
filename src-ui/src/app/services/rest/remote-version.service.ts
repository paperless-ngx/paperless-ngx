import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'

export interface AppRemoteVersion {
  version: string
  update_available: boolean
}

export interface AppRelease {
  version: string
  name: string
  body_html: string
  html_url: string
  published_at: string
}

export interface AppReleaseNotes {
  version: string
  releases: AppRelease[]
  stars: number | null
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

  public getReleaseNotes(since?: string): Observable<AppReleaseNotes> {
    let params = new HttpParams()
    if (since) {
      params = params.set('since', since)
    }
    return this.http.get<AppReleaseNotes>(
      `${environment.apiBaseUrl}release_notes/`,
      { params }
    )
  }
}
