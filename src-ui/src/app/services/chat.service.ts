import {
  HttpClient,
  HttpDownloadProgressEvent,
  HttpEventType,
} from '@angular/common/http'
import { inject, Injectable } from '@angular/core'
import { filter, map, Observable } from 'rxjs'
import { environment } from 'src/environments/environment'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private http: HttpClient = inject(HttpClient)

  streamChat(documentId: number, prompt: string): Observable<string> {
    return this.http
      .post(
        `${environment.apiBaseUrl}documents/chat/`,
        {
          document_id: documentId,
          q: prompt,
        },
        {
          observe: 'events',
          reportProgress: true,
          responseType: 'text',
          withCredentials: true,
        }
      )
      .pipe(
        map((event) => {
          if (event.type === HttpEventType.DownloadProgress) {
            return (event as HttpDownloadProgressEvent).partialText!
          }
        }),
        filter((chunk) => !!chunk)
      )
  }
}
