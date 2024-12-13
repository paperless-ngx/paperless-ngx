import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import {
  PaperlessUserProfile,
  SocialAccountProvider,
  TotpSettings,
} from '../data/user-profile'

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

  getTotpSettings(): Observable<TotpSettings> {
    return this.http.get<TotpSettings>(
      `${environment.apiBaseUrl}${this.endpoint}/totp/`
    )
  }

  activateTotp(
    totpSecret: string,
    totpCode: string
  ): Observable<{ success: boolean; recovery_codes: string[] }> {
    return this.http.post<{ success: boolean; recovery_codes: string[] }>(
      `${environment.apiBaseUrl}${this.endpoint}/totp/`,
      {
        secret: totpSecret,
        code: totpCode,
      }
    )
  }

  deactivateTotp(): Observable<boolean> {
    return this.http.delete<boolean>(
      `${environment.apiBaseUrl}${this.endpoint}/totp/`,
      {}
    )
  }
}
