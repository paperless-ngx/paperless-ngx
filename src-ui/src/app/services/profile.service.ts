import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'
import {
  AccountSessionRedirect,
  AccountSessionsResponse,
  PaperlessUserProfile,
  SocialAccountProvider,
  TotpSettings,
} from '../data/user-profile'

@Injectable({
  providedIn: 'root',
})
export class ProfileService {
  private http = inject(HttpClient)

  private endpoint = 'profile'

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

  /** Loads the accounts available for quick switching. */
  getAccountSessions(): Observable<AccountSessionsResponse> {
    return this.http.get<AccountSessionsResponse>(
      `${environment.apiBaseUrl}${this.endpoint}/sessions/`
    )
  }

  /** Starts authentication for adding an account to quick switching. */
  addAccountSession(): Observable<AccountSessionRedirect> {
    return this.http.post<AccountSessionRedirect>(
      `${environment.apiBaseUrl}${this.endpoint}/sessions/add/`,
      {}
    )
  }

  /** Requests activation of an enrolled user's session. */
  switchAccountSession(userId: number): Observable<AccountSessionRedirect> {
    return this.http.post<AccountSessionRedirect>(
      `${environment.apiBaseUrl}${this.endpoint}/sessions/switch/`,
      { user_id: userId }
    )
  }

  /** Removes and logs out an account saved for quick switching. */
  removeAccountSession(userId: number): Observable<AccountSessionRedirect> {
    return this.http.delete<AccountSessionRedirect>(
      `${environment.apiBaseUrl}${this.endpoint}/sessions/${userId}/`
    )
  }

  /** Logs out the active account and returns the next destination. */
  logoutCurrentAccountSession(): Observable<AccountSessionRedirect> {
    return this.http.post<AccountSessionRedirect>(
      `${environment.apiBaseUrl}${this.endpoint}/sessions/logout/`,
      {}
    )
  }

  /** Logs out every account enrolled for quick switching. */
  logoutAllAccountSessions(): Observable<AccountSessionRedirect> {
    return this.http.post<AccountSessionRedirect>(
      `${environment.apiBaseUrl}${this.endpoint}/sessions/logout_all/`,
      {}
    )
  }
}
