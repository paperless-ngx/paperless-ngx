import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { environment } from 'src/environments/environment'

export interface DjangoMessage {
  level: string
  message: string
  tags: string
}

@Injectable({
  providedIn: 'root',
})
export class MessagesService {
  private endpoint = 'messages'

  constructor(private http: HttpClient) {}

  get(): Observable<DjangoMessage[]> {
    return this.http.get<DjangoMessage[]>(
      `${environment.apiBaseUrl}${this.endpoint}/`
    )
  }
}
