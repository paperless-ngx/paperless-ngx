import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { PaperlessUserProfile } from '../data/user-profile'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class ProfileService {
  private endpoint = 'profile'

  constructor(private http: HttpClient) {}

  get(): Observable<PaperlessUserProfile> {
    return this.http.get<PaperlessUserProfile>(
      `${environment.apiBaseUrl}${this.endpoint}/`
    )
  }

  update(profile: PaperlessUserProfile): Observable<PaperlessUserProfile> {
    return this.http.patch<PaperlessUserProfile>(
      `${environment.apiBaseUrl}${this.endpoint}/`,
      profile
    )
  }

  generateAuthToken(): Observable<string> {
    return this.http.post<string>(
      `${environment.apiBaseUrl}${this.endpoint}/generate_auth_token/`,
      {}
    )
  }
}
