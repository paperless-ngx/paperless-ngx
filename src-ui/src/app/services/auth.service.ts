import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { map } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from 'src/environments/environment';

interface TokenResponse {
  token: string
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {

  private currentUsername: string

  private token: string

  constructor(private http: HttpClient, private router: Router) { 
    this.token = localStorage.getItem('auth-service:token')
    if (this.token == null) {
      this.token = sessionStorage.getItem('auth-service:token')
    }
    this.currentUsername = localStorage.getItem('auth-service:currentUsername')
    if (this.currentUsername == null) {
      this.currentUsername = sessionStorage.getItem('auth-service:currentUsername')
    }
  }


  private requestToken(username: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${environment.apiBaseUrl}token/`, {"username": username, "password": password})
  }

  isAuthenticated(): boolean {
    return this.currentUsername != null
  }

  logout() {
    this.currentUsername = null
    this.token = null
    localStorage.removeItem('auth-service:token')
    localStorage.removeItem('auth-service:currentUsername')
    sessionStorage.removeItem('auth-service:token')
    sessionStorage.removeItem('auth-service:currentUsername')
    this.router.navigate(['login'])
  }

  login(username: string, password: string, rememberMe: boolean): Observable<boolean> {
    return this.requestToken(username,password).pipe(
      map(tokenResponse => {
        this.currentUsername = username
        this.token = tokenResponse.token
        if (rememberMe) {
          localStorage.setItem('auth-service:token', this.token)
          localStorage.setItem('auth-service:currentUsername', this.currentUsername)
        } else {
          sessionStorage.setItem('auth-service:token', this.token)
          sessionStorage.setItem('auth-service:currentUsername', this.currentUsername)
        }
        return true
      })
    )
  }

  getToken(): string {
    return this.token
  }

  getCurrentUsername(): string {
    return this.currentUsername
  }
}
