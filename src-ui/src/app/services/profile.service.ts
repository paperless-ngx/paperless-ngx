import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import {
  EdocUserProfile,
  SocialAccountProvider,
} from '../data/user-profile'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class ProfileService {
  private endpoint = 'profile'

  constructor(private http: HttpClient) {}

  get(): Observable<EdocUserProfile> {
    return this.http.get<EdocUserProfile>(
      `${environment.apiBaseUrl}${this.endpoint}/`
    )
  }

  update(profile: EdocUserProfile): Observable<EdocUserProfile> {
    return this.http.patch<EdocUserProfile>(
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

  disconnectSocialAccount(id: number): Observable<number> {
    return this.http.post<number>(
      `${environment.apiBaseUrl}${this.endpoint}/disconnect_social_account/`,
      { id: id }
    )
  }

  getSocialAccountProviders(): Observable<SocialAccountProvider[]> {
    return this.http.get<SocialAccountProvider[]>(
      `${environment.apiBaseUrl}${this.endpoint}/social_account_providers/`
    )
  }
}
